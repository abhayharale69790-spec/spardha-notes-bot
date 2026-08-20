"""34-Channel Source Discovery Audit Script (Metadata Inspection Only, No Downloads)."""

import asyncio
from datetime import datetime, timezone, timedelta
import json
import logging
from pathlib import Path
import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telethon import TelegramClient
from telethon.tl.types import MessageMediaDocument, DocumentAttributeFilename
from config.settings import get_settings
from database.session import get_session, init_db
from database.models import ChannelAuthStatus
from collectors.telegram_channel_registry import telegram_channel_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()


async def audit_discovery():
    await init_db()
    
    print("=" * 135)
    print(" 📡 34-CHANNEL SOURCE DISCOVERY AUDIT (METADATA-ONLY INSPECTION)")
    print(f" 📅 Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(" 🔒 Mode: Read-Only Metadata Inspection (NO downloads, NO branding, NO reposting)")
    print("=" * 135 + "\n")

    client = TelegramClient("data/telegram_user_session", settings.telegram_api_id, settings.telegram_api_hash)
    await client.connect()
    is_auth = await client.is_user_authorized()
    if not is_auth:
        print("❌ Telethon user client is not authorized.")
        return

    me = await client.get_me()
    print(f"✅ Telethon Collector Connected as: {me.first_name} (ID: {me.id})\n")

    async with get_session() as session:
        sources = await telegram_channel_registry.get_all_approved_sources(session)

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    audit_results = []

    print("🔍 Inspecting 34 approved channels...")
    for idx, s in enumerate(sources, 1):
        uname = s.channel_username or str(s.channel_id)
        target = s.channel_username or s.channel_id
        
        info = {
            "index": idx,
            "username": f"@{s.channel_username}" if s.channel_username else str(s.channel_id),
            "category": s.exam_category.value,
            "auth_status": s.authorization_status.value,
            "accessible": "No",
            "historical_access": "No",
            "latest_msg_id": "N/A",
            "latest_date": "N/A",
            "msgs_last_30d": 0,
            "pdf_count_sample": 0,
            "sample_size": 0,
            "pdf_yield_pct": 0.0,
            "estimated_pdf_yield": "Low",
            "recommended_backfill": 50,
            "title": s.title,
        }

        try:
            entity = await client.get_entity(target)
            info["accessible"] = "Yes"
            info["title"] = getattr(entity, "title", s.title)

            # Sample up to 100 recent messages for metadata inspection
            sample_messages = []
            async for msg in client.iter_messages(entity, limit=100):
                sample_messages.append(msg)

            if sample_messages:
                info["historical_access"] = "Yes"
                latest_m = sample_messages[0]
                info["latest_msg_id"] = str(latest_m.id)
                if latest_m.date:
                    info["latest_date"] = latest_m.date.strftime("%Y-%m-%d")

                info["sample_size"] = len(sample_messages)
                
                # Count msgs in last 30 days & PDFs
                pdf_count = 0
                msgs_30d = 0
                for m in sample_messages:
                    if m.date and m.date.replace(tzinfo=timezone.utc if m.date.tzinfo is None else m.date.tzinfo) >= thirty_days_ago:
                        msgs_30d += 1
                    
                    if m.media and isinstance(m.media, MessageMediaDocument) and m.document:
                        mime = getattr(m.document, "mime_type", "")
                        fname = ""
                        for attr in m.document.attributes:
                            if isinstance(attr, DocumentAttributeFilename):
                                fname = attr.file_name or ""
                        if mime == "application/pdf" or fname.lower().endswith(".pdf"):
                            pdf_count += 1

                info["msgs_last_30d"] = msgs_30d
                info["pdf_count_sample"] = pdf_count
                yield_pct = (pdf_count / len(sample_messages)) * 100 if sample_messages else 0
                info["pdf_yield_pct"] = round(yield_pct, 1)

                if yield_pct >= 20 or pdf_count >= 15:
                    info["estimated_pdf_yield"] = "High (★★★★★)"
                    info["recommended_backfill"] = 150
                elif yield_pct >= 8 or pdf_count >= 6:
                    info["estimated_pdf_yield"] = "Medium (★★★☆☆)"
                    info["recommended_backfill"] = 100
                elif pdf_count > 0:
                    info["estimated_pdf_yield"] = "Moderate (★★☆☆☆)"
                    info["recommended_backfill"] = 50
                else:
                    info["estimated_pdf_yield"] = "Low/Text (★☆☆☆☆)"
                    info["recommended_backfill"] = 30

        except Exception as e:
            info["accessible"] = "No"
            info["estimated_pdf_yield"] = f"Error: {str(e)[:25]}"

        audit_results.append(info)
        print(f" [{idx:2d}/34] {info['username']:<35} | Access: {info['accessible']:<3} | PDFs: {info['pdf_count_sample']:2d}/100 | Yield: {info['estimated_pdf_yield']}")
        await asyncio.sleep(0.35)

    await client.disconnect()

    # Save discovery json
    with open("data/source_discovery_audit.json", "w", encoding="utf-8") as f:
        json.dump(audit_results, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 135)
    print(" 📊 COMPLETE 34-CHANNEL AUDIT REPORT")
    print("=" * 135)


if __name__ == "__main__":
    asyncio.run(audit_discovery())
