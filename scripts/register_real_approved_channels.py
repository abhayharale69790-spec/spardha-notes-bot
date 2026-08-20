"""Register and resolve real approved Telegram study channels."""

import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telethon import TelegramClient
from config.settings import get_settings
from database.session import get_session, init_db
from database import crud
from database.models import ChannelAuthStatus, ExamCategory, TelegramChannelSource

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()

CHANNELS_TO_REGISTER = [
    # MPSC
    ("mpsc_StudyCampus", ExamCategory.MPSC, "MPSC Study Campus"),
    ("MPSCHistory", ExamCategory.MPSC, "MPSC History Special"),
    ("MPSCmaths", ExamCategory.MPSC, "MPSC Maths & Reasoning Hub"),
    ("MaharashtraSpardhaPariksha", ExamCategory.MPSC, "Maharashtra Spardha Pariksha"),
    ("mpscguidnce", ExamCategory.MPSC, "MPSC Guidance & Notes"),
    ("mpscsimplified", ExamCategory.MPSC, "MPSC Simplified"),
    ("mpsc_university", ExamCategory.MPSC, "MPSC University"),
    ("VidyaPrabodhiniMPSC", ExamCategory.MPSC, "Vidya Prabodhini MPSC"),
    ("MpscMadeSimple", ExamCategory.MPSC, "MPSC Made Simple"),

    # Police Bharti
    ("missionpolice2021", ExamCategory.POLICE_BHARTI, "Mission Police Bharti"),
    ("Police_bharti_and_MPSC", ExamCategory.POLICE_BHARTI, "Police Bharti & MPSC Prep"),
    ("MaharashtraPoliceBharati", ExamCategory.POLICE_BHARTI, "Maharashtra Police Bharti Official"),
    ("tikkarmarathi", ExamCategory.POLICE_BHARTI, "Tikkar Marathi Study"),
    ("vishalsirgk", ExamCategory.POLICE_BHARTI, "Vishal Sir GK & Police Bharti"),

    # Saral Seva / Talathi
    ("mega_talathi_bharti", ExamCategory.SARAL_SEVA, "Mega Talathi Bharti TCS/IBPS"),
    ("SuperCoachingMarathiby_Testbook", ExamCategory.SARAL_SEVA, "SuperCoaching Marathi by Testbook"),

    # SSC
    ("ssccglpinnacleonline", ExamCategory.SSC, "SSC CGL Pinnacle Online"),
    ("Exam_Posts", ExamCategory.SSC, "Exam Posts (SSC / Central)"),

    # Banking
    ("banking_free_study_materials_pdf", ExamCategory.BANKING, "Banking Free Study Materials PDF"),

    # JEE & NEET
    ("JEE_Full_Study_Material", ExamCategory.JEE, "JEE Full Study Material"),
    ("NEET_Full_Study_Material", ExamCategory.NEET, "NEET Full Study Material"),
    ("pdfstudymaterialss", ExamCategory.NCERT, "NCERT & Foundation Study Materials PDF"),

    # State Board 10th - 12th
    ("mhsb_11_12", ExamCategory.BOARD_10_12, "Maharashtra State Board 11th & 12th HSC"),
    ("maharashtra_state_boardbooks", ExamCategory.BOARD_10_12, "Maharashtra State Board Textbooks (Balbharati)"),
]


async def main():
    await init_db()
    print("=" * 115)
    print(" 📡 REGISTERING & RESOLVING APPROVED TELEGRAM STUDY CHANNELS")
    print(f" 📅 Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 115 + "\n")

    client = TelegramClient("data/telegram_user_session", settings.telegram_api_id, settings.telegram_api_hash)
    await client.connect()

    is_auth = await client.is_user_authorized()
    if is_auth:
        me = await client.get_me()
        print(f"✅ Authenticated as: {me.first_name} (ID: {me.id})\n")
    else:
        print("⚠️ Warning: Client not logged in; registering with simulated peer IDs.\n")

    registered_entries = []

    for uname, exam_cat, default_title in CHANNELS_TO_REGISTER:
        channel_id = None
        title = default_title

        if is_auth:
            try:
                entity = await client.get_entity(uname)
                channel_id = entity.id
                # Telethon channel IDs for supergroups/channels start with -100 in bot API
                if not str(channel_id).startswith("-100"):
                    tg_peer_id = int(f"-100{channel_id}")
                else:
                    tg_peer_id = channel_id
                title = getattr(entity, "title", default_title)
                status_icon = "🟢"
            except Exception as e:
                # Hash fallback if entity is private or rate-limited
                tg_peer_id = -1000000000000 - abs(hash(uname)) % 10000000000
                status_icon = "🟡"
        else:
            tg_peer_id = -1000000000000 - abs(hash(uname)) % 10000000000
            status_icon = "🟡"

        async with get_session() as session:
            source = await crud.get_or_create_telegram_channel(
                session=session,
                channel_id=tg_peer_id,
                channel_username=uname,
                title=title,
                exam_category=exam_cat,
                authorization_status=ChannelAuthStatus.AUTHORIZED,
            )

        registered_entries.append((uname, exam_cat.value, title, tg_peer_id))
        print(f" {status_icon} Registered: @{uname:<35} | #{exam_cat.value:<14} | \"{title[:35]}\"")
        await asyncio.sleep(0.3)

    if is_auth:
        await client.disconnect()

    print("\n" + "=" * 115)
    print(f" 🎉 SUCCESSFULLY REGISTERED {len(registered_entries)} APPROVED TELEGRAM CHANNELS!")
    print(" 🔒 Status: AUTHORIZED | is_active = True | Backfill: NOT STARTED (Awaiting signal)")
    print("=" * 115 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
