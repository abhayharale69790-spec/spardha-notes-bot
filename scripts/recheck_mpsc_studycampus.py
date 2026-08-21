"""Re-check @mpsc_StudyCampus with MTProto."""

import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys

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
)
from collectors.telegram_user_collector import telegram_user_collector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main():
    await init_db()

    ready = await telegram_user_collector.initialize_client()
    if not ready:
        print("❌ Failed to initialize MTProto client.")
        return

    client = telegram_user_collector.client
    channel_username = "mpsc_StudyCampus"

    print("=" * 120)
    print(f" 🔍 DEEP MTPROTO INSPECTION: @{channel_username}")
    print(f" 📅 Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 120 + "\n")

    try:
        entity = await client.get_entity(channel_username)
        print(f"✅ Entity Resolved: Title='{entity.title}', ID={entity.id}, Username=@{entity.username}")

        # Fetch latest 10 messages
        messages = []
        async for m in client.iter_messages(entity, limit=10):
            messages.append(m)

        print(f"\n📑 Retrieved {len(messages)} latest messages from @{channel_username}:")
        print("─" * 120)
        print(f"{'MSG ID':<8} | {'DATE (UTC)':<20} | {'MEDIA TYPE':<22} | {'TEXT / CAPTION SNIPPET'}")
        print("─" * 120)

        for m in messages:
            media_type = type(m.media).__name__ if m.media else "None (Text)"
            date_str = m.date.strftime("%Y-%m-%d %H:%M:%S") if m.date else "N/A"
            text_snippet = (m.text or "").replace("\n", " ")[:60]
            print(f"#{m.id:<7} | {date_str:<20} | {media_type:<22} | {text_snippet}")

        print("─" * 120)

        # Check latest date
        if messages:
            latest_msg = messages[0]
            latest_date = latest_msg.date
            now = datetime.now(timezone.utc)
            days_ago = (now - latest_date).days if latest_date else 9999

            print(f"\n📊 Latest Message ID: #{latest_msg.id}")
            print(f"📅 Latest Message Date: {latest_date.strftime('%Y-%m-%d %H:%M:%S UTC')} ({days_ago} days ago)")

            # Check if there are documents around checkpoint #1802
            print(f"\n🔍 Inspecting messages around checkpoint #1802...")
            checkpoint_msgs = []
            async for cm in client.iter_messages(entity, min_id=1790, max_id=1810):
                checkpoint_msgs.append(cm)

            for cm in checkpoint_msgs:
                c_media = type(cm.media).__name__ if cm.media else "Text"
                c_date = cm.date.strftime("%Y-%m-%d") if cm.date else "N/A"
                print(f"   Msg #{cm.id} ({c_date}, {c_media}): {(cm.text or '')[:50]}")

            # Decision logic
            async with get_session() as session:
                job = await crud.get_latest_backfill_job(session)
                task_stmt = select(BackfillChannelTask).where(
                    BackfillChannelTask.job_id == job.id,
                    BackfillChannelTask.channel_username == channel_username,
                )
                res = await session.execute(task_stmt)
                task = res.scalar_one_or_none()

                if task:
                    print(f"\n📋 Current DB Task #{task.id} for @{channel_username}: Status={task.status.value}, Checkpoint=#{task.last_successful_msg_id}")

                    # If the channel has genuine historical study content or was an intentional base source:
                    # Restore task to queue with checkpoint preserved
                    print(f"\n🔄 Restoring @{channel_username} to QUEUED (IN_PROGRESS/PENDING) with checkpoint #{task.last_successful_msg_id}...")
                    
                    task.status = BackfillTaskStatus.IN_PROGRESS if task.last_successful_msg_id > 0 else BackfillTaskStatus.PENDING
                    task.error_message = None
                    session.add(task)

                    # Update job total_channels
                    all_tasks_stmt = select(BackfillChannelTask).where(
                        BackfillChannelTask.job_id == job.id,
                        BackfillChannelTask.status.in_([BackfillTaskStatus.PENDING, BackfillTaskStatus.IN_PROGRESS, BackfillTaskStatus.COMPLETED]),
                    )
                    active_tasks = (await session.execute(all_tasks_stmt)).scalars().all()
                    
                    job.total_channels = len(active_tasks)
                    session.add(job)
                    await session.commit()
                    print(f"✅ Restored! Updated Job #{job.id} active channels count to: {len(active_tasks)}")

    except Exception as e:
        logger.error(f"Error inspecting @{channel_username}: {e}", exc_info=True)
    finally:
        if client and client.is_connected():
            await client.disconnect()
        await telegram_user_collector.bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
