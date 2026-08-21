"""Verify Database State and Inspect Ingested Telegram Study Materials."""

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

from sqlalchemy import select
from database.session import init_db, get_session
from database.models import StudyMaterial, TelegramChannelSource, ChannelAuthStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main():
    await init_db()
    async with get_session() as session:
        # 1. Fetch all Telegram sources and progress
        ch_res = await session.execute(select(TelegramChannelSource))
        channels = ch_res.scalars().all()

        # 2. Fetch all materials
        mat_res = await session.execute(select(StudyMaterial).order_by(StudyMaterial.id.asc()))
        all_materials = mat_res.scalars().all()

    tg_materials = [m for m in all_materials if m.source_name and "Telegram" in m.source_name]

    print("=" * 135)
    print(" 🔍 DATABASE INTEGRITY & INGESTION STATE AUDIT")
    print(f" 📅 Audit Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 135 + "\n")

    print(f"📊 Total Study Materials in Database: {len(all_materials)}")
    print(f"📡 Total Ingested from Telegram      : {len(tg_materials)}\n")

    # Verify integrity of each record
    corrupt_count = 0
    clean_count = 0

    print("=" * 135)
    print(" 📑 INGESTED TELEGRAM STUDY MATERIALS (INTEGRITY CHECK)")
    print("=" * 135)
    print(f"{'ID':<5} | {'TITLE':<45} | {'CATEGORY':<12} | {'PAGES':<6} | {'STATUS':<9} | {'FILE_ID':<15} | {'HASH':<12} | {'SOURCE'}")
    print("─" * 135)

    for m in tg_materials:
        has_file_id = bool(m.telegram_file_id)
        has_hash = bool(m.content_hash)
        has_pages = m.page_count is not None and m.page_count > 0
        is_clean = has_pages and has_hash and m.status == "VERIFIED"

        if is_clean:
            clean_count += 1
            clean_icon = "✅"
        else:
            corrupt_count += 1
            clean_icon = "❌"

        fid_display = f"{m.telegram_file_id[:12]}..." if m.telegram_file_id else "None"
        hash_display = f"{m.content_hash[:10]}..." if m.content_hash else "None"
        title_display = m.title[:42] + "..." if len(m.title) > 42 else m.title

        print(f"{clean_icon} #{m.id:<3} | {title_display:<45} | #{m.exam_category.value:<11} | {m.page_count:<6} | {m.status:<9} | {fid_display:<15} | {hash_display:<12} | {m.source_name}")

    print("─" * 135)
    print(f"✅ Verified Clean Materials : {clean_count}")
    print(f"❌ Corrupt / Partial Records : {corrupt_count}")

    print("\n" + "=" * 135)
    print(" 📡 TELEGRAM CHANNEL SCAN PROGRESS & CHECKPOINTS")
    print("=" * 135)
    print(f"{'#':<3} | {'USERNAME':<32} | {'CATEGORY':<12} | {'LAST SCANNED MSG':<18} | {'VERIFIED INGESTED':<18} | {'STATUS'}")
    print("─" * 135)

    for idx, c in enumerate(channels, 1):
        uname = f"@{c.channel_username}" if c.channel_username else f"ID {c.channel_id}"
        print(f"{idx:2d}. | {uname:<32} | #{c.exam_category.value:<11} | #{c.last_scanned_msg_id:<17} | {c.total_verified:<18} | {c.authorization_status.value}")

    print("=" * 135 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
