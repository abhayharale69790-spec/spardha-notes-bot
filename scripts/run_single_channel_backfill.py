"""Run targeted historical backfill for an approved Telegram channel."""

import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import get_settings
from database.session import get_session, init_db
from database import crud
from collectors.telegram_user_collector import telegram_user_collector
from services.coverage_engine import coverage_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()


async def run_backfill(channel_username: str, limit: int = 100):
    await init_db()
    clean_username = channel_username.replace("@", "").strip()

    print("=" * 115)
    print(f" 🚀 EXECUTING TELEGRAM MTPROTO BACKFILL FOR: @{clean_username}")
    print(f" 🎯 Message Limit: {limit} | Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 115 + "\n")

    # 1. Look up channel in database
    async with get_session() as session:
        ch = await crud.get_telegram_channel_by_username(session, clean_username)
        if not ch:
            print(f"❌ Error: Channel @{clean_username} is not registered in the approved database registry.")
            return

        print(f"📡 Found Approved Channel: '{ch.title}'")
        print(f"   • Database ID      : {ch.id}")
        print(f"   • Peer ID          : {ch.channel_id}")
        print(f"   • Exam Category    : #{ch.exam_category.value}")
        print(f"   • Auth Status      : {ch.authorization_status.value}")
        print(f"   • Last Scanned Msg : #{ch.last_scanned_msg_id}\n")

    # 2. Connect Telethon Client
    print("🔐 Connecting Telegram MTProto User Client...")
    is_ready = await telegram_user_collector.initialize_client()
    if not is_ready:
        print("❌ Telethon user client initialization failed. Check session authentication.")
        return

    me = await telegram_user_collector.client.get_me()
    print(f"✅ Telethon Collector Connected as: {me.first_name} (ID: {me.id})\n")

    # 3. Execute Scan & Ingestion
    print(f"📥 Scanning last {limit} messages from @{clean_username} for study PDFs...")
    print("─" * 115)

    ingested_count = await telegram_user_collector.scan_channel_messages(
        channel_source=ch,
        limit=limit,
    )

    print("─" * 115)
    print(f"\n✅ Backfill Scan Completed! Total New Study Materials Ingested: {ingested_count}")

    # 4. Trigger Syllabus Coverage Matrix Recalculation
    print("\n📊 Recalculating Syllabus Coverage Matrix...")
    matrix = await coverage_engine.compute_coverage_matrix(force_refresh=True)
    mpsc_metrics = matrix.exam_matrices.get(ch.exam_category)

    if mpsc_metrics:
        print(f"   • #{ch.exam_category.value} Total Verified Materials : {mpsc_metrics.total_materials}")
        print(f"   • #{ch.exam_category.value} Coverage Score         : {mpsc_metrics.coverage_score:.1f}%")
        print(f"   • Readiness Status                  : {mpsc_metrics.status.value}")


    print("\n" + "=" * 115)
    print(" 🏁 BACKFILL OPERATION COMPLETED SUCCESSFULLY")
    print("=" * 115 + "\n")

    if telegram_user_collector.client and telegram_user_collector.client.is_connected():
        await telegram_user_collector.client.disconnect()


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "mpsc_StudyCampus"
    msg_limit = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 100
    asyncio.run(run_backfill(target, msg_limit))
