"""Audit and Refine Paused Mass Backfill Queue.

Audits all 42 queued channels against live MTProto accessibility, recent activity,
database authorization, and 3rd-stage quality validation benchmarks.
Disables/skips unvalidated, inaccessible, or placeholder channels while preserving checkpoints.
"""

import asyncio
from datetime import datetime, timezone, timedelta
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update
from telethon.errors import ChannelPrivateError, UsernameNotOccupiedError, UsernameInvalidError

from database.session import init_db, get_session
from database import crud
from database.models import (
    BackfillJob,
    BackfillJobStatus,
    BackfillChannelTask,
    BackfillTaskStatus,
    ChannelAuthStatus,
    TelegramChannelSource,
)
from collectors.telegram_user_collector import telegram_user_collector
from collectors.telegram_channel_registry import DEFAULT_APPROVED_CHANNELS

VALIDATION_FILE = Path("data/third_stage_validation_results.json")
SECOND_STAGE_FILE = Path("data/second_stage_audit_ranked.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main():
    await init_db()

    # Load 3rd stage validation approved list
    approved_usernames: Set[str] = set()
    validation_scores: Dict[str, float] = {}
    if VALIDATION_FILE.exists():
        with open(VALIDATION_FILE, encoding="utf-8") as f:
            v_data = json.load(f)
            for item in v_data:
                clean_u = item.get("clean_username", "").lower()
                validation_scores[clean_u] = item.get("validation_score", 0.0)
                if item.get("is_approved"):
                    approved_usernames.add(clean_u)

    # Base approved channels
    base_approved_usernames: Set[str] = {
        cfg.channel_username.strip().replace("@", "").lower()
        for cfg in DEFAULT_APPROVED_CHANNELS
        if cfg.channel_username
    }

    # Connect MTProto client
    client_ready = await telegram_user_collector.initialize_client()
    if not client_ready:
        print("❌ MTProto Client failed to initialize. Aborting audit.")
        return

    client = telegram_user_collector.client

    async with get_session() as session:
        job = await crud.get_latest_backfill_job(session)
        if not job:
            print("❌ No backfill job found in database.")
            return

        tasks = await crud.get_backfill_tasks_for_job(session, job.id)

    print("=" * 145)
    print(" 🔍 COMPREHENSIVE 42-CHANNEL BACKFILL QUEUE AUDIT")
    print(f" 📅 Audit Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f" 📋 Job UUID: {job.job_uuid} (Job ID: #{job.id}, Status: {job.status.value})")
    print("=" * 145 + "\n")

    valid_channels_count = 0
    skipped_channels_count = 0
    audit_results: List[Dict[str, Any]] = []

    for idx, task in enumerate(tasks, 1):
        uname = (task.channel_username or "").strip().replace("@", "").lower()
        uname_display = f"@{task.channel_username}" if task.channel_username else f"ID {task.channel_id}"

        is_base = uname in base_approved_usernames
        is_validated_top = uname in approved_usernames
        val_score = validation_scores.get(uname, 100.0 if is_base else 0.0)

        # Check live accessibility & recent activity via MTProto
        accessible = False
        latest_msg_id = 0
        latest_date_str = "N/A"
        active_recent = False
        rejection_reason = ""

        try:
            entity = await client.get_entity(task.channel_username or task.channel_id)
            accessible = True

            # Fetch latest message
            async for m in client.iter_messages(entity, limit=1):
                if m:
                    latest_msg_id = m.id
                    if m.date:
                        latest_date_str = m.date.strftime("%Y-%m-%d")
                        # Active within 180 days
                        if datetime.now(timezone.utc) - m.date < timedelta(days=180):
                            active_recent = True
                        else:
                            rejection_reason = f"Stale channel (Inactive > 180 days, last: {latest_date_str})"
                break
        except (UsernameNotOccupiedError, ValueError):
            accessible = False
            rejection_reason = "Channel username does not exist on Telegram"
        except ChannelPrivateError:
            accessible = False
            rejection_reason = "Channel is private / restricted"
        except Exception as e:
            accessible = False
            rejection_reason = f"Access error: {str(e)[:50]}"

        # Authorization & validation check
        is_legit_source = is_base or is_validated_top
        if accessible and active_recent and not is_legit_source:
            rejection_reason = "Unverified candidate (Pending review, not in validated top tier)"

        # Final decision
        will_keep = accessible and active_recent and is_legit_source

        if will_keep:
            final_status = BackfillTaskStatus.IN_PROGRESS if task.last_successful_msg_id > 0 else BackfillTaskStatus.PENDING
            action_str = "KEEP (QUEUED)"
            valid_channels_count += 1
            # Update DB task
            async with get_session() as session:
                task_stmt = (
                    update(BackfillChannelTask)
                    .where(BackfillChannelTask.id == task.id)
                    .values(status=final_status, error_message=None, updated_at=datetime.now(timezone.utc))
                )
                await session.execute(task_stmt)
                await session.commit()
        else:
            final_status = BackfillTaskStatus.SKIPPED
            action_str = f"SKIP ({rejection_reason})"
            skipped_channels_count += 1
            # Update DB task to SKIPPED
            async with get_session() as session:
                task_stmt = (
                    update(BackfillChannelTask)
                    .where(BackfillChannelTask.id == task.id)
                    .values(status=BackfillTaskStatus.SKIPPED, error_message=rejection_reason, updated_at=datetime.now(timezone.utc))
                )
                await session.execute(task_stmt)
                await session.commit()

        audit_results.append({
            "idx": idx,
            "username": uname_display,
            "title": task.title,
            "category": task.exam_category.value,
            "accessible": accessible,
            "latest_msg_id": latest_msg_id,
            "latest_date": latest_date_str,
            "val_score": val_score,
            "is_approved": is_legit_source,
            "checkpoint": task.last_successful_msg_id,
            "action": action_str,
            "final_status": final_status.value,
            "will_keep": will_keep,
        })

    # Update job total_channels count in DB
    async with get_session() as session:
        job_stmt = (
            update(BackfillJob)
            .where(BackfillJob.id == job.id)
            .values(total_channels=valid_channels_count, updated_at=datetime.now(timezone.utc))
        )
        await session.execute(job_stmt)
        await session.commit()

    # Print Full Audit Table
    print(f"{'#':<3} | {'USERNAME':<34} | {'CAT':<11} | {'ACC':<4} | {'LATEST MSG (DATE)':<22} | {'SCORE':<6} | {'CHECKPOINT':<11} | {'DECISION / ACTION'}")
    print("─" * 145)

    for res in audit_results:
        acc_icon = "✅" if res["accessible"] else "❌"
        msg_date_str = f"#{res['latest_msg_id']} ({res['latest_date']})" if res["latest_msg_id"] else "None"
        dec_icon = "🟢" if res["will_keep"] else "🚫"
        score_str = f"{res['val_score']:.1f}" if res["val_score"] else "0.0"

        print(f"{res['idx']:2d}. | {res['username']:<34} | #{res['category']:<10} | {acc_icon} | {msg_date_str:<22} | {score_str:<6} | #{res['checkpoint']:<10} | {dec_icon} {res['action']}")

    print("─" * 145)
    print(f"📊 Total Queued Channels Audited : {len(tasks)}")
    print(f"🟢 Approved & Retained Channels   : {valid_channels_count}")
    print(f"🚫 Disabled / Skipped Channels   : {skipped_channels_count}")
    print(f"🔒 Checkpoints Preserved         : 100% of retained channels\n")

    # Print Clean Final List of Retained Channels
    print("=" * 145)
    print(f" 📋 FINAL CLEAN BACKFILL CHANNELS QUEUE ({valid_channels_count} CHANNELS)")
    print("=" * 145)
    print(f"{'#':<3} | {'USERNAME':<34} | {'CATEGORY':<12} | {'TITLE':<42} | {'CHECKPOINT':<12} | {'STATUS'}")
    print("─" * 145)

    retained_idx = 1
    for res in audit_results:
        if res["will_keep"]:
            title_display = res["title"][:40] + "..." if len(res["title"]) > 40 else res["title"]
            print(f"{retained_idx:2d}. | {res['username']:<34} | #{res['category']:<11} | {title_display:<42} | #{res['checkpoint']:<11} | {res['final_status']}")
            retained_idx += 1

    print("=" * 145 + "\n")

    # Cleanup telethon
    if client and client.is_connected():
        await client.disconnect()
    await telegram_user_collector.bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
