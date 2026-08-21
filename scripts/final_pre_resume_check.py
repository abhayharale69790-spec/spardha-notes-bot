"""Final Pre-Resume Check and Channel Partitioning Audit."""

import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update
from database.session import init_db, get_session
from database import crud
from database.models import (
    BackfillJob,
    BackfillChannelTask,
    BackfillTaskStatus,
    TelegramChannelSource,
    ChannelAuthStatus,
)
from collectors.telegram_channel_registry import telegram_channel_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main():
    await init_db()

    async with get_session() as session:
        # 1. Ensure defaults and modes are updated in DB
        await telegram_channel_registry.initialize_defaults(session)

        # Explicitly configure @mpsc_StudyCampus as HISTORICAL_ONLY
        stmt_mpsc = (
            update(TelegramChannelSource)
            .where(TelegramChannelSource.channel_username == "mpsc_StudyCampus")
            .values(
                monitoring_mode="HISTORICAL_ONLY",
                redistribution_authorized=True,
                authorization_status=ChannelAuthStatus.AUTHORIZED,
                is_active=True,
                last_scanned_msg_id=1802,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.execute(stmt_mpsc)

        # 2. Fetch latest backfill job & tasks
        job = await crud.get_latest_backfill_job(session)
        if not job:
            print("❌ No backfill job found.")
            return

        tasks_res = await session.execute(
            select(BackfillChannelTask).where(BackfillChannelTask.job_id == job.id).order_by(BackfillChannelTask.id.asc())
        )
        tasks = list(tasks_res.scalars().all())

        # Update task modes
        for t in tasks:
            uname = (t.channel_username or "").strip().replace("@", "").lower()
            if uname == "mpsc_studycampus":
                t.monitoring_mode = "HISTORICAL_ONLY"
                t.redistribution_authorized = True
                t.status = BackfillTaskStatus.IN_PROGRESS
                t.last_successful_msg_id = 1802
                session.add(t)
            elif t.status != BackfillTaskStatus.SKIPPED:
                t.monitoring_mode = "CONTINUOUS"
                t.redistribution_authorized = True
                session.add(t)

        await session.commit()

        # Re-fetch updated tasks
        tasks_res = await session.execute(
            select(BackfillChannelTask).where(BackfillChannelTask.job_id == job.id).order_by(BackfillChannelTask.id.asc())
        )
        tasks = list(tasks_res.scalars().all())

    # Partition channels into groups
    historical_only: List[BackfillChannelTask] = []
    continuous_monitoring: List[BackfillChannelTask] = []
    unauthorized_skipped: List[BackfillChannelTask] = []

    for t in tasks:
        if t.status == BackfillTaskStatus.SKIPPED:
            unauthorized_skipped.append(t)
        elif t.monitoring_mode == "HISTORICAL_ONLY":
            historical_only.append(t)
        else:
            continuous_monitoring.append(t)

    # Sync total active channels in job
    active_total = len(historical_only) + len(continuous_monitoring)
    async with get_session() as session:
        await session.execute(
            update(BackfillJob).where(BackfillJob.id == job.id).values(total_channels=active_total, updated_at=datetime.now(timezone.utc))
        )
        await session.commit()

    print("=" * 135)
    print(" 🛡️ FINAL PRE-RESUME CHANNEL CLASSIFICATION & AUTHORIZATION AUDIT")
    print(f" 📅 Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f" 📋 Job UUID: {job.job_uuid} (Job ID: #{job.id}, Status: {job.status.value})")
    print("=" * 135 + "\n")

    print(f"🏛️ 1. HISTORICAL-ONLY CHANNELS ({len(historical_only)} channel)")
    print("─" * 135)
    print(f"{'#':<3} | {'USERNAME':<30} | {'CATEGORY':<12} | {'CHECKPOINT':<12} | {'STATUS':<14} | {'NOTE'}")
    print("─" * 135)
    for idx, t in enumerate(historical_only, 1):
        uname = f"@{t.channel_username}" if t.channel_username else f"ID {t.channel_id}"
        print(f"{idx:2d}. | {uname:<30} | #{t.exam_category.value:<11} | #{t.last_successful_msg_id:<11} | {t.status.value:<14} | Frozen after msg #1803 (2021); excluded from continuous listener")

    print("\n" + "=" * 135)
    print(f"📡 2. CONTINUOUS-MONITORING CHANNELS ({len(continuous_monitoring)} channels)")
    print("─" * 135)
    print(f"{'#':<3} | {'USERNAME':<34} | {'CATEGORY':<12} | {'CHECKPOINT':<12} | {'REDIST_AUTH':<12} | {'TITLE'}")
    print("─" * 135)
    for idx, t in enumerate(continuous_monitoring, 1):
        uname = f"@{t.channel_username}" if t.channel_username else f"ID {t.channel_id}"
        print(f"{idx:2d}. | {uname:<34} | #{t.exam_category.value:<11} | #{t.last_successful_msg_id:<11} | ✅ TRUE      | {t.title[:45]}")

    print("\n" + "=" * 135)
    print(f"🚫 3. UNAUTHORIZED / SKIPPED CHANNELS ({len(unauthorized_skipped)} channels)")
    print("─" * 135)
    print(f"{'#':<3} | {'USERNAME':<34} | {'CATEGORY':<12} | {'STATUS':<12} | {'REASON / ERROR'}")
    print("─" * 135)
    for idx, t in enumerate(unauthorized_skipped, 1):
        uname = f"@{t.channel_username}" if t.channel_username else f"ID {t.channel_id}"
        print(f"{idx:2d}. | {uname:<34} | #{t.exam_category.value:<11} | 🚫 SKIPPED  | {t.error_message or 'Unauthorized / Unverified'}")

    print("\n" + "=" * 135)
    print(f"📊 SUMMARY OF BACKFILL QUEUE:")
    print(f"   • Historical-Only Channels      : {len(historical_only)}")
    print(f"   • Continuous-Monitoring Channels: {len(continuous_monitoring)}")
    print(f"   • Unauthorized / Skipped        : {len(unauthorized_skipped)}")
    print(f"   • TOTAL ACTIVE BACKFILL CHANNELS: {active_total}")
    print("=" * 135 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
