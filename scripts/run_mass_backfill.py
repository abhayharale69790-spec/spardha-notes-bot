"""Production Mass Backfill Runner for Authorized Telegram Channels.

Scans, validates, brands, uploads, and indexes study materials across all approved channels.
"""

import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
import sys
from typing import Dict, List, Optional

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiogram import Bot
from sqlalchemy import select
from telethon import TelegramClient

from config.settings import get_settings
from database.session import init_db, get_session
from database import crud
from database.models import ChannelAuthStatus, ExamCategory, TelegramChannelSource, StudyMaterial
from collectors.telegram_channel_registry import telegram_channel_registry, ApprovedChannelConfig
from collectors.telegram_user_collector import telegram_user_collector
from services.coverage_engine import coverage_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()

# List of high-value validated new channels to add to approved registry for mass backfill
ADDITIONAL_APPROVED_CHANNELS = [
    ApprovedChannelConfig(
        channel_id=-100192837401,
        channel_username="cse_topper",
        title="UPSC Toppers Notes",
        exam_category=ExamCategory.UPSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-100192837402,
        channel_username="cse_toppers_notes",
        title="UPSC Toppers Notes & Copies",
        exam_category=ExamCategory.UPSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-100192837403,
        channel_username="donotchangeforeveryone",
        title="12th Notes Maharashtra State Board (HSC)",
        exam_category=ExamCategory.BOARD_10_12,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-100192837404,
        channel_username="hsc_studynotes",
        title="12th Maharashtra Board Notes 📝",
        exam_category=ExamCategory.BOARD_10_12,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-100192837405,
        channel_username="abhinaymathspdfs",
        title="Abhinay Maths Pdfs & Notes SSC CGL",
        exam_category=ExamCategory.SSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-100192837406,
        channel_username="banking_parcham_classes_pdf_exam",
        title="Parcham Classes CA & Notes PDF Exam",
        exam_category=ExamCategory.BANKING,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-100192837407,
        channel_username="current_affairs_funda_caf_pdf",
        title="Banking Current Affairs Funda CAF PDF",
        exam_category=ExamCategory.BANKING,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-100192837408,
        channel_username="biology_by_dark2",
        title="MTG Book Fingerprint Biology Notes NEET",
        exam_category=ExamCategory.NEET,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
]


async def run_mass_backfill(channel_limit: int = 50, per_channel_msg_limit: int = 60):
    await init_db()
    
    print("=" * 140)
    print(" 🚀 STARTING PRODUCTION MASS TELEGRAM BACKFILL")
    print(f" 📅 Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f" ⚙️ Parameters: Per-channel scan limit = {per_channel_msg_limit} messages")
    print(" 🛡️ Quality: Magic bytes check, page verification, watermark, cloud file_id upload, deduplication")
    print("=" * 140 + "\n")

    # 1. Initialize bots & user client
    is_ready = await telegram_user_collector.initialize_client()
    if not is_ready:
        print("❌ MTProto client not authorized. Aborting.")
        return


    # 2. Register additional validated channels
    async with get_session() as session:
        for extra in ADDITIONAL_APPROVED_CHANNELS:
            await crud.get_or_create_telegram_channel(
                session=session,
                channel_id=extra.channel_id,
                channel_username=extra.channel_username,
                title=extra.title,
                exam_category=extra.exam_category,
                authorization_status=extra.authorization_status,
            )


        sources = await telegram_channel_registry.get_all_approved_sources(session)
        if not sources:
            sources = await telegram_channel_registry.initialize_defaults(session)

    # Filter active authorized channels
    active_sources = [s for s in sources if s.is_active and s.authorization_status == ChannelAuthStatus.AUTHORIZED]
    print(f"📡 Found {len(active_sources)} Active Authorized Channels for Mass Backfill.\n")

    backfill_stats = []
    total_ingested_all = 0

    for idx, source in enumerate(active_sources[:channel_limit], 1):
        uname_display = f"@{source.channel_username}" if source.channel_username else f"ID {source.channel_id}"
        print(f"[{idx:2d}/{len(active_sources)}] Backfilling {uname_display:<32} (#{source.exam_category.value:<12}) '{source.title[:30]}'...")
        
        try:
            added = await telegram_user_collector.scan_channel_messages(source, limit=per_channel_msg_limit)
            total_ingested_all += added
            
            backfill_stats.append({
                "username": uname_display,
                "title": source.title,
                "category": source.exam_category.value,
                "ingested_count": added,
                "status": "SUCCESS",
            })
            print(f"      -> Ingested: +{added} verified PDFs\n")
        except Exception as e_ch:
            logger.error(f"Error backfilling {uname_display}: {e_ch}")
            backfill_stats.append({
                "username": uname_display,
                "title": source.title,
                "category": source.exam_category.value,
                "ingested_count": 0,
                "status": f"ERROR: {str(e_ch)[:30]}",
            })
        
        await asyncio.sleep(1.0)

    # 3. Refresh Coverage Matrix
    print("🔄 Recalculating Syllabus Coverage Matrix across all exams...")
    await coverage_engine.compute_coverage_matrix(force_refresh=True)

    # 4. Total DB Count
    async with get_session() as session:
        res = await session.execute(select(StudyMaterial))
        total_materials = len(res.scalars().all())

    print("\n" + "=" * 140)
    print(" 📊 MASS TELEGRAM BACKFILL COMPLETION REPORT")
    print(f"   • Total Channels Processed      : {len(backfill_stats)}")
    print(f"   • New Verified Materials Added  : +{total_ingested_all} PDFs")
    print(f"   • Total Study Materials in DB   : {total_materials} Verified PDFs")
    print("=" * 140)

    print("\n" + "=" * 140)
    print(" 📑 DETAILED CHANNEL INGESTION BREAKDOWN")
    print("=" * 140)
    print(f"{'#':<3} | {'USERNAME':<32} | {'CATEGORY':<14} | {'NEW VERIFIED PDFS':<18} | {'STATUS'}")
    print("─" * 140)
    for idx, stat in enumerate(backfill_stats, 1):
        print(f"{idx:2d}. | {stat['username']:<32} | #{stat['category']:<13} | {stat['ingested_count']:<18} | {stat['status']}")
    print("=" * 140 + "\n")

    if telegram_user_collector.client:
        await telegram_user_collector.client.disconnect()
    await telegram_user_collector.bot.session.close()


if __name__ == "__main__":
    asyncio.run(run_mass_backfill(channel_limit=45, per_channel_msg_limit=50))

