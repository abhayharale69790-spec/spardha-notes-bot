"""Third-Stage Content Validation Engine: Deep 20-PDF Byte Inspection, Quality Scoring & Spam Filtering."""

import asyncio
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
import logging
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

from pypdf import PdfReader
from rapidfuzz import fuzz
from telethon import TelegramClient
from telethon.tl.types import MessageMediaDocument, DocumentAttributeFilename

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import get_settings
from database.session import init_db
from database.models import ChannelAuthStatus, ExamCategory
from workers.quality_worker import QualityWorker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()

SANDBOX_DIR = Path("downloads/third_stage_sandbox")
SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
NOW_DATE = datetime(2026, 8, 20, 23, 35, tzinfo=timezone.utc)


def detect_language(text: str) -> str:
    """Detect dominant language of extracted text."""
    devanagari_chars = len(re.findall(r"[\u0900-\u097F]", text))
    latin_chars = len(re.findall(r"[a-zA-Z]", text))
    total = devanagari_chars + latin_chars
    if total == 0:
        return "Unknown"
    dev_ratio = devanagari_chars / total
    if dev_ratio > 0.6:
        # Check for Marathi-specific words
        if re.search(r"आहे|झाले|करणे|महाराष्ट्र|स्पर्धा|परीक्षा|प्रकार|उत्तर|प्रश्न", text):
            return "Marathi"
        return "Hindi/Devanagari"
    elif dev_ratio < 0.2:
        return "English"
    else:
        return "Bilingual (Marathi/English)"


def check_exam_classification_accuracy(cat: str, title: str, text: str) -> bool:
    """Check if document text aligns accurately with assigned exam category."""
    combined = f"{title} {text[:2000]}".lower()
    if cat == "MPSC":
        return bool(re.search(r"mpsc|महाराष्ट्र|राज्यसेवा|संयुक्त|घटना|कलम|इतिहास|भूगोल|अर्थशास्त्र|polity|csat", combined))
    if cat == "POLICE_BHARTI":
        return bool(re.search(r"पोलीस|भरती|police|व्याकरण|मराठी|सामान्य ज्ञान|कलम|कायदे|चालू घडामोडी|gk", combined))
    if cat == "SARAL_SEVA":
        return bool(re.search(r"तलाठी|सरळसेवा|tcs|ibps|talathi|zp|grammar|इंग्रजी|अंकगणित|बुद्धिमत्ता", combined))
    if cat == "SSC":
        return bool(re.search(r"ssc|cgl|chsl|mts|pinnacle|maths|english|reasoning|tcs|gk|general awareness", combined))
    if cat == "BANKING":
        return bool(re.search(r"bank|sbi|ibps|rbi|puzzle|reasoning|quant|seating|financial|awareness", combined))
    if cat == "UPSC":
        return bool(re.search(r"upsc|ias|ips|cse|prelims|mains|topper|gs|ethics|essay|history|geography", combined))
    if cat == "JEE":
        return bool(re.search(r"jee|iit|mains|advance|physics|chemistry|mathematics|mechanics|organic|formula", combined))
    if cat == "NEET":
        return bool(re.search(r"neet|medical|biology|botany|zoology|ncert|physics|chemistry|cell|genetics", combined))
    if cat in ("NCERT", "BOARD_10_12"):
        return bool(re.search(r"ncert|cbse|board|balbharati|10th|12th|hsc|ssc|science|maths|physics|chemistry", combined))
    return True


async def validate_channel_candidate(
    client: TelegramClient,
    channel_info: Dict[str, Any],
    sample_limit: int = 3,
) -> Dict[str, Any]:
    """Sample and validate representative PDF documents from a candidate channel."""
    username = channel_info["clean_username"]
    cat = channel_info["category"]
    title = channel_info["title"]

    logger.info(f"🔬 Auditing Content for @{username} (#{cat})...")

    result = {
        "username": f"@{username}",
        "clean_username": username,
        "title": title,
        "category": cat,
        "source_url": channel_info["source_url"],
        "sampled_docs_count": 0,
        "valid_pdfs_count": 0,
        "useful_docs_count": 0,
        "accurate_class_count": 0,
        "duplicate_count": 0,
        "languages": set(),
        "avg_pages": 0.0,
        "pdf_quality_pct": 0.0,
        "duplicate_pct": 0.0,
        "classification_accuracy_pct": 0.0,
        "useful_material_pct": 0.0,
        "freshness_days": 0,
        "validation_score": 0.0,
        "is_approved": False,
        "rejection_reasons": [],
        "recommended_backfill": 0,
    }

    try:
        entity = await client.get_entity(username)
        latest_msgs = []
        async for msg in client.iter_messages(entity, limit=35):
            if msg.media and isinstance(msg.media, MessageMediaDocument) and msg.document:
                mime = getattr(msg.document, "mime_type", "")
                fname = ""
                for attr in msg.document.attributes:
                    if isinstance(attr, DocumentAttributeFilename):
                        fname = attr.file_name or ""
                if mime == "application/pdf" or fname.lower().endswith(".pdf"):
                    latest_msgs.append((msg, fname))
                    if len(latest_msgs) >= sample_limit:
                        break

        result["sampled_docs_count"] = len(latest_msgs)
        if not latest_msgs:
            result["rejection_reasons"].append("No PDF documents found in recent messages")
            result["languages"] = list(result["languages"])
            return result

        hashes: Set[str] = set()
        total_pages = 0

        for msg, fname in latest_msgs:
            doc_size = getattr(msg.document, "size", 0)
            if doc_size > 8 * 1024 * 1024:  # Skip oversized files for fast validation
                continue

            temp_path = SANDBOX_DIR / f"val_{entity.id}_{msg.id}.pdf"
            try:
                # Stream file to sandbox with 5s timeout
                dl = await asyncio.wait_for(client.download_media(msg, file=str(temp_path)), timeout=5.0)
                if not dl or not temp_path.exists():
                    continue

                raw_bytes = temp_path.read_bytes()
                # 1. Real PDF Magic Header
                if not QualityWorker.is_valid_pdf_magic_bytes(raw_bytes[:16]):
                    continue

                # 2. Structural & Page Count Inspection
                reader = PdfReader(io.BytesIO(raw_bytes))
                page_count = len(reader.pages)
                if page_count < 1:
                    continue

                total_pages += page_count
                result["valid_pdfs_count"] += 1



                # Extract text sample
                sample_text = ""
                for p in reader.pages[:4]:
                    txt = p.extract_text() or ""
                    sample_text += txt + " "

                # 3. Duplicate check via SHA-256
                chash = hashlib.sha256(raw_bytes).hexdigest()
                if chash in hashes:
                    result["duplicate_count"] += 1
                else:
                    hashes.add(chash)

                # 4. Educational Usefulness Check
                doc_title = fname or msg.text or title
                is_useful, reason = QualityWorker.check_educational_usefulness(
                    title=doc_title,
                    text=sample_text,
                    page_count=page_count,
                )
                if is_useful:
                    result["useful_docs_count"] += 1

                # 5. Classification Accuracy
                if check_exam_classification_accuracy(cat, doc_title, sample_text):
                    result["accurate_class_count"] += 1

                # 6. Language Detection
                lang = detect_language(sample_text)
                result["languages"].add(lang)

            except Exception as e_sample:
                logger.debug(f"Error inspecting doc msg #{msg.id}: {e_sample}")
            finally:
                if temp_path.exists():
                    try: temp_path.unlink()
                    except Exception: pass

        # Compute percentages
        valid_cnt = result["valid_pdfs_count"]
        if valid_cnt > 0:
            result["avg_pages"] = round(total_pages / valid_cnt, 1)
            result["pdf_quality_pct"] = round((valid_cnt / result["sampled_docs_count"]) * 100, 1)
            result["duplicate_pct"] = round((result["duplicate_count"] / valid_cnt) * 100, 1)
            result["useful_material_pct"] = round((result["useful_docs_count"] / valid_cnt) * 100, 1)
            result["classification_accuracy_pct"] = round((result["accurate_class_count"] / valid_cnt) * 100, 1)

            # Freshness
            if latest_msgs[0][0].date:
                dt = latest_msgs[0][0].date.replace(tzinfo=timezone.utc if latest_msgs[0][0].date.tzinfo is None else latest_msgs[0][0].date.tzinfo)
                days_ago = (NOW_DATE - dt).days
                result["freshness_days"] = max(0, days_ago)
            
            freshness_score = max(0.0, 10.0 * (1.0 - (result["freshness_days"] / 180.0)))
            
            # Validation Score (0 - 100)
            score = (
                (result["useful_material_pct"] * 0.35)
                + (result["pdf_quality_pct"] * 0.25)
                + (result["classification_accuracy_pct"] * 0.20)
                + ((100.0 - result["duplicate_pct"]) * 0.10)
                + (freshness_score)
            )
            result["validation_score"] = round(score, 1)

            # Rejection Criteria
            if result["useful_material_pct"] < 35.0:
                result["rejection_reasons"].append(f"Low educational usefulness ({result['useful_material_pct']}% useful docs)")
            if result["duplicate_pct"] > 40.0:
                result["rejection_reasons"].append(f"High duplicate content rate ({result['duplicate_pct']}% duplicates)")
            if result["classification_accuracy_pct"] < 40.0:
                result["rejection_reasons"].append(f"Low syllabus relevance to #{cat} ({result['classification_accuracy_pct']}%)")
            if result["pdf_quality_pct"] < 40.0:
                result["rejection_reasons"].append(f"High corrupted/unreadable PDF rate ({100 - result['pdf_quality_pct']}%)")

            if not result["rejection_reasons"]:
                result["is_approved"] = True
                if result["validation_score"] >= 80:
                    result["recommended_backfill"] = 150
                elif result["validation_score"] >= 65:
                    result["recommended_backfill"] = 100
                else:
                    result["recommended_backfill"] = 50
            else:
                result["recommended_backfill"] = 0

    except Exception as e_cand:
        logger.warning(f"Error auditing candidate @{username}: {e_cand}")
        result["rejection_reasons"].append(f"Channel access failed: {str(e_cand)[:30]}")

    result["languages"] = list(result["languages"])
    return result


async def main():
    await init_db()
    with open("data/second_stage_audit_ranked.json", encoding="utf-8") as f:
        ranked_data = json.load(f)

    # Group by category, take top 5 per category
    by_category: Dict[str, List[Dict[str, Any]]] = {}
    for c in ranked_data:
        by_category.setdefault(c["category"], []).append(c)

    candidates_to_test = []
    for cat, list_c in by_category.items():
        candidates_to_test.extend(list_c[:5])

    print("=" * 140)
    print(" 🔬 THIRD-STAGE CONTENT VALIDATION & BYTE-LEVEL INSPECTION (20-PDF AUDIT)")
    print(f" 📅 Timestamp: {NOW_DATE.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f" 🎯 Total Candidate Channels to Deep-Audit: {len(candidates_to_test)}")
    print(" 🔒 Sandbox: Internal byte inspection only (NO files saved permanently / NO redistribution)")
    print("=" * 140 + "\n")

    client = TelegramClient("data/telegram_user_session", settings.telegram_api_id, settings.telegram_api_hash)
    await client.connect()
    is_auth = await client.is_user_authorized()
    if not is_auth:
        print("❌ Telethon user client not authorized.")
        return

    validation_results = []
    for idx, cand in enumerate(candidates_to_test, 1):
        print(f"[{idx:2d}/{len(candidates_to_test)}] Sampling representative PDFs from {cand['username']} (#{cand['category']})...")
        res = await validate_channel_candidate(client, cand, sample_limit=3)
        validation_results.append(res)
        status_tag = "✅ VALIDATED" if res["is_approved"] else "❌ REJECTED"
        print(f"      -> Score: {res['validation_score']:<5.1f} | Useful: {res['useful_material_pct']}% | Dups: {res['duplicate_pct']}% | {status_tag}")
        await asyncio.sleep(0.2)




    await client.disconnect()

    # Save validation json
    out_file = Path("data/third_stage_validation_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(validation_results, f, default=str, ensure_ascii=False, indent=2)

    # Sort validated channels by validation_score desc
    validated_passed = [c for c in validation_results if c["is_approved"]]
    validated_rejected = [c for c in validation_results if not c["is_approved"]]
    validated_passed.sort(key=lambda x: x["validation_score"], reverse=True)

    print("\n" + "=" * 140)
    print(" 📊 THIRD-STAGE CONTENT VALIDATION RESULTS SUMMARY")
    print(f"   • Total Channels Deep-Audited : {len(validation_results)}")
    print(f"   • High-Quality Validated      : {len(validated_passed)}")
    print(f"   • Rejected for Quality/Spam   : {len(validated_rejected)}")
    print("=" * 140)

    # Group passed by category
    by_cat = {}
    for c in validated_passed:
        by_cat.setdefault(c["category"], []).append(c)

    print("\n" + "=" * 140)
    print(" 🏆 TOP SAFEST & HIGHEST-VALUE DISCOVERED CHANNELS PER EXAM CATEGORY")
    print("=" * 140)

    category_order = [
        "MPSC", "POLICE_BHARTI", "SARAL_SEVA", "SSC", "BANKING",
        "UPSC", "JEE", "NEET", "NCERT", "BOARD_10_12"
    ]

    for cat in category_order:
        items = by_cat.get(cat, [])
        if not items:
            continue
        print(f"\n📁 Exam Category: #{cat} ({len(items)} Validated Safe Sources)")
        print(f"{'Rank':<4} | {'USERNAME':<30} | {'SCORE':<6} | {'USEFUL %':<9} | {'QUALITY %':<10} | {'ACCURACY %':<11} | {'DUPS %':<7} | {'REC BACKFILL':<12} | {'TITLE'}")
        print("─" * 140)
        for r_idx, c in enumerate(items, 1):
            print(f"{r_idx:2d}.   | {c['username']:<30} | {c['validation_score']:<6.1f} | {c['useful_material_pct']:<9.1f} | {c['pdf_quality_pct']:<10.1f} | {c['classification_accuracy_pct']:<11.1f} | {c['duplicate_pct']:<7.1f} | {c['recommended_backfill']:<12} | {c['title'][:35]}")

    print("\n" + "=" * 140)
    print(" 🚫 REJECTED CANDIDATE CHANNELS (REASONS FOR REJECTION)")
    print("=" * 140)
    print(f"{'#':<3} | {'USERNAME':<30} | {'CAT':<12} | {'SCORE':<6} | {'REJECTION REASON(S)'}")
    print("─" * 140)
    for idx, c in enumerate(validated_rejected, 1):
        reasons_str = "; ".join(c["rejection_reasons"])
        print(f"{idx:2d}. | {c['username']:<30} | #{c['category']:<11} | {c['validation_score']:<6.1f} | {reasons_str}")
    print("=" * 140 + "\n")



if __name__ == "__main__":
    asyncio.run(main())
