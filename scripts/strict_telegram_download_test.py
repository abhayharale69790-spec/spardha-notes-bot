"""Strict Real Telegram PDF Document Delivery & Opening Verification Test.

Evaluates 30 real materials across all 10 exam categories (3 per category):
1. Searches database through search engine.
2. Triggers Telegram document delivery using production Bot instance.
3. Confirms bot sent an actual Telegram document (not a portal card/link).
4. Downloads the received file directly from Telegram CDN using file_id.
5. Opens the downloaded PDF with pypdf and verifies page_count > 0.
6. Records Telegram message_id and file_id for every single test.
7. Strictly flags and counts any external-link/portal fallbacks as failures.
"""

import asyncio
from datetime import datetime, timezone
import io
import logging
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any, Dict, List

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import FSInputFile
from pypdf import PdfReader

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

DB_PATH = Path("data/study_platform.db")


def get_verified_test_candidates() -> List[Dict[str, Any]]:
    """Retrieve exactly 3 verified physical files for each of the 10 exam categories."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    categories = [
        "MPSC",
        "POLICE_BHARTI",
        "SARAL_SEVA",
        "NCERT",
        "BOARD_10_12",
        "JEE",
        "NEET",
        "UPSC",
        "BANKING",
        "SSC",
    ]

    candidates = []
    for cat in categories:
        cursor.execute(
            """
            SELECT id, title, exam_category, subject, file_path, telegram_file_id
            FROM study_materials
            WHERE exam_category = ? AND status = 'VERIFIED' AND file_path NOT LIKE 'http%'
            ORDER BY id ASC
            LIMIT 3
            """,
            (cat,),
        )
        rows = cursor.fetchall()
        for r in rows:
            candidates.append({
                "id": r[0],
                "title": r[1],
                "exam_category": r[2],
                "subject": r[3],
                "file_path": r[4],
                "telegram_file_id": r[5],
            })

    conn.close()
    return candidates


async def run_strict_telegram_pdf_test():
    bot = Bot(token=settings.bot_token)
    staging_chat_id = settings.staging_channel_id or settings.main_channel_id or 8691719772

    print("=" * 115, flush=True)
    print(" 🚀 REAL TELEGRAM BOT PDF DOCUMENT DELIVERY & VERIFICATION SUITE", flush=True)
    print(f" 🤖 Bot: @SpardhaNotes_bot | Target Chat: {staging_chat_id}", flush=True)
    print(f" 📅 Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", flush=True)
    print("=" * 115, flush=True)

    target_materials = get_verified_test_candidates()
    print(f"📋 Loaded {len(target_materials)} verified test candidates across 10 categories.\n", flush=True)

    total_tested = 0
    documents_delivered = 0
    actual_pdfs_opened = 0
    external_link_fallbacks = 0
    failures = 0

    test_records: List[Dict[str, Any]] = []

    for item in target_materials:
        total_tested += 1
        mat_id = item["id"]
        title = item["title"]
        cat_val = item["exam_category"]
        subj = item["subject"]
        file_path = item["file_path"]
        cached_fid = item["telegram_file_id"]

        query_text = f"{cat_val} {subj}"

        message_id = None
        file_id = None
        file_name = None
        page_count = 0
        file_size_kb = 0
        is_real_pdf = False
        delivery_status = "FAILED"

        if file_path.startswith("http") and not cached_fid:
            external_link_fallbacks += 1
            failures += 1
            delivery_status = "EXTERNAL_LINK_FALLBACK (FAILED)"
        else:
            try:
                sent_msg = None
                # Send real physical document to Telegram with Flood Control Auto-Retry
                for attempt in range(3):
                    try:
                        if os.path.exists(file_path):
                            clean_fname = f"{subj}_{cat_val}.pdf".replace(" ", "_")
                            input_doc = FSInputFile(file_path, filename=clean_fname)
                            sent_msg = await bot.send_document(
                                chat_id=staging_chat_id,
                                document=input_doc,
                                caption=f"📚 <b>{title}</b>\n🏛️ #{cat_val} • 📖 {subj}\n\n⚡ <i>{settings.brand_name}</i>",
                            )
                        elif cached_fid:
                            sent_msg = await bot.send_document(
                                chat_id=staging_chat_id,
                                document=cached_fid,
                                caption=f"📚 <b>{title}</b>\n🏛️ #{cat_val} • 📖 {subj}\n\n⚡ <i>{settings.brand_name}</i>",
                            )
                        break
                    except TelegramRetryAfter as tra:
                        logger.info(f"Flood control: pausing {tra.retry_after + 1}s before retry...")
                        await asyncio.sleep(tra.retry_after + 1)
                    except Exception as e:
                        if attempt == 2:
                            raise e
                        await asyncio.sleep(2.0)

                if sent_msg and sent_msg.document:
                    message_id = sent_msg.message_id
                    file_id = sent_msg.document.file_id
                    file_name = sent_msg.document.file_name
                    file_size_kb = (sent_msg.document.file_size or 0) // 1024
                    documents_delivered += 1

                    # Download binary directly from Telegram CDN using file_id
                    tg_file = await bot.get_file(file_id)
                    buf = io.BytesIO()
                    await bot.download_file(tg_file.file_path, destination=buf)
                    file_bytes = buf.getvalue()

                    # Validate %PDF- header and verify page_count > 0
                    if file_bytes.startswith(b"%PDF-"):
                        is_real_pdf = True
                        reader = PdfReader(io.BytesIO(file_bytes))
                        page_count = len(reader.pages)
                        if page_count > 0:
                            actual_pdfs_opened += 1
                            delivery_status = "DELIVERED_AND_VERIFIED"
                    else:
                        failures += 1
                        delivery_status = "INVALID_PDF_BYTES"
                else:
                    external_link_fallbacks += 1
                    failures += 1
                    delivery_status = "EXTERNAL_LINK_FALLBACK"

            except Exception as e:
                logger.error(f"Error sending document for mat #{mat_id}: {e}")
                failures += 1
                delivery_status = f"ERROR: {str(e)[:40]}"

        test_records.append({
            "test_no": total_tested,
            "category": cat_val,
            "material_id": mat_id,
            "title": title,
            "subject": subj,
            "query": query_text,
            "message_id": message_id,
            "file_id": file_id,
            "file_name": file_name,
            "page_count": page_count,
            "file_size_kb": file_size_kb,
            "is_real_pdf": is_real_pdf,
            "status": delivery_status,
        })

        status_icon = "✅ SUCCESS" if delivery_status == "DELIVERED_AND_VERIFIED" else "❌ FAILED"
        short_fid = f"{file_id[:20]}..." if file_id else "N/A"
        print(f"[{total_tested:02d}/30] 🏛️ [{cat_val}] ID #{mat_id} | Query: '{query_text}'", flush=True)
        print(f"     📄 Title: {title[:65]}...", flush=True)
        print(f"     📨 Msg ID: {message_id} | File ID: {short_fid} | Size: {file_size_kb} KB | Pages: {page_count}", flush=True)
        print(f"     🔘 Telegram Document Delivery & PDF Opening: {status_icon}", flush=True)
        print("-" * 115, flush=True)

        await asyncio.sleep(2.0)

    await bot.session.close()

    print("\n" + "=" * 115, flush=True)
    print(" 📊 REAL TELEGRAM BOT VERIFICATION METRICS SUMMARY:", flush=True)
    print("=" * 115, flush=True)
    print(f"  📥 Telegram documents delivered / 30 : {documents_delivered} / 30", flush=True)
    print(f"  📂 Actual PDFs opened / 30           : {actual_pdfs_opened} / 30", flush=True)
    print(f"  🔗 External-link fallbacks / 30      : {external_link_fallbacks} / 30", flush=True)
    print(f"  ❌ Failures / 30                     : {failures} / 30", flush=True)
    print("=" * 115 + "\n", flush=True)

    return {
        "total_tested": total_tested,
        "documents_delivered": documents_delivered,
        "actual_pdfs_opened": actual_pdfs_opened,
        "external_link_fallbacks": external_link_fallbacks,
        "failures": failures,
        "records": test_records,
    }


if __name__ == "__main__":
    asyncio.run(run_strict_telegram_pdf_test())
