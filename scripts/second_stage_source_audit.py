"""Second-Stage Telegram Source Audit & Multi-Factor Ranking Engine."""

from datetime import datetime, timezone, timedelta
import json
import logging
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

from rapidfuzz import fuzz

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import get_settings
from database.session import init_db
from database.models import ChannelAuthStatus, ExamCategory

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

NOW_DATE = datetime(2026, 8, 20, 23, 30, tzinfo=timezone.utc)
STALENESS_CUTOFF_DAYS = 180
STALENESS_DATE = NOW_DATE - timedelta(days=STALENESS_CUTOFF_DAYS)


def parse_date(date_str: str) -> Optional[datetime]:
    if not date_str or date_str == "N/A":
        return None
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def calculate_channel_scores(item: Dict[str, Any], all_titles: List[str]) -> Tuple[float, Dict[str, float], bool, str]:
    """Calculate 4-factor score:

    - Recent Activity (30%)
    - PDF Yield (30%)
    - Educational Usefulness (25%)
    - Source Diversity (15%)
    """
    latest_dt = parse_date(item.get("latest_date"))
    
    # 1. Staleness filter (< 180 days)
    if not latest_dt or latest_dt < STALENESS_DATE:
        days_ago = (NOW_DATE - latest_dt).days if latest_dt else 999
        return 0.0, {}, False, f"Stale/Inactive (Last active {days_ago} days ago)"

    if item.get("accessible") != "Yes":
        return 0.0, {}, False, "Inaccessible / Private"

    pdf_sample = item.get("pdf_count_sample", 0)
    pdf_pct = item.get("pdf_yield_pct", 0.0)
    if pdf_sample == 0 or pdf_pct == 0:
        return 0.0, {}, False, "Zero study PDFs in sample"

    # Factor 1: Recent Activity Score (30 pts max)
    days_since_active = (NOW_DATE - latest_dt).days
    recency_factor = max(0.0, 1.0 - (days_since_active / STALENESS_CUTOFF_DAYS))
    vol_factor = min(1.0, item.get("msgs_last_30d", 0) / 40.0)
    # Give base recency even for low volume if updated recently
    activity_score = 30.0 * (recency_factor * 0.7 + vol_factor * 0.3)

    # Factor 2: PDF Yield Score (30 pts max)
    yield_score = 30.0 * min(1.0, pdf_pct / 85.0)

    # Factor 3: Educational Usefulness Score (25 pts max)
    title_text = f"{item.get('title', '')} {item.get('username', '')}".lower()
    edu_kw_matches = 0
    edu_patterns = [
        r"notes|नोट्स|handwritten|topper",
        r"pyq|question|paper|प्रश्नपत्रिका|प्रश्नसंच",
        r"syllabus|अभ्यासक्रम|pattern|tcs|ibps",
        r"formula|सूत्र|grammar|व्याकरण|rules",
        r"ncert|solution|balbharati|board|mcq",
        r"current affairs|चालू घडामोडी|gk|capsule",
    ]
    for p in edu_patterns:
        if re.search(p, title_text):
            edu_kw_matches += 1
    usefulness_score = 25.0 * min(1.0, (edu_kw_matches + 1.5) / 4.0)

    # Factor 4: Source Diversity Score (15 pts max)
    diversity_score = 15.0
    if item.get("related_channel") and "Related to" in item.get("related_channel", ""):
        diversity_score = 7.5  # Partial penalty for clone/mirror network

    # Near duplicate check with existing titles in batch
    for other_title in all_titles:
        if other_title != item.get("title") and fuzz.token_set_ratio(item.get("title", ""), other_title) >= 90:
            diversity_score = min(diversity_score, 8.0)
            break

    total_score = round(activity_score + yield_score + usefulness_score + diversity_score, 1)
    
    breakdown = {
        "activity": round(activity_score, 1),
        "yield": round(yield_score, 1),
        "usefulness": round(usefulness_score, 1),
        "diversity": round(diversity_score, 1),
        "total": total_score,
    }
    return total_score, breakdown, True, "Active & Verified Educational Source"


def map_coverage_gaps(cat: str, title: str, username: str) -> List[str]:
    """Map channel to target syllabus coverage gaps."""
    t = f"{title} {username}".lower()
    gaps = []
    
    if cat == "MPSC":
        if re.search(r"current|चालू घडामोडी|daily", t): gaps.append("MPSC Current Affairs & Yearly Digests")
        if re.search(r"pyq|paper|प्रश्नपत्रिका|combine", t): gaps.append("MPSC Prelims & Combine PYQ Banks")
        if re.search(r"topper|handwritten|notes|राज्यशास्त्र|polity", t): gaps.append("MPSC State Polity & Economy Notes")
        if not gaps: gaps.append("MPSC General Studies Comprehensive Subject Packs")

    elif cat == "POLICE_BHARTI":
        if re.search(r"grammar|व्याकरण|मराठी", t): gaps.append("Police Bharti Marathi Grammar & Vocab")
        if re.search(r"pyq|paper|प्रश्नसंच", t): gaps.append("Maharashtra Police Bharti Solved PYQs")
        if re.search(r"gk|general|विशेष", t): gaps.append("Police Bharti Static GK & Law Provisions")
        if not gaps: gaps.append("Police Bharti Mock Tests & Practice Sets")

    elif cat == "SARAL_SEVA":
        if re.search(r"tcs|ibps|pattern", t): gaps.append("TCS/IBPS Pattern Talathi & ZP Question Sets")
        if re.search(r"grammar|english|मराठी", t): gaps.append("Saral Seva English & Marathi Grammar")
        if not gaps: gaps.append("Saral Seva Aptitude & District PYQs")

    elif cat == "SSC":
        if re.search(r"math|formula|advanced", t): gaps.append("SSC CGL Advanced Maths & Formula Compendiums")
        if re.search(r"grammar|english|rules", t): gaps.append("SSC English 120 Rules & Vocab")
        if re.search(r"pinnacle|mcq|tcs", t): gaps.append("Pinnacle 6800+ TCS Question Banks")
        if not gaps: gaps.append("SSC General Awareness & Reasoning")

    elif cat == "BANKING":
        if re.search(r"puzzle|reasoning", t): gaps.append("IBPS/SBI High Level Puzzles & Seating")
        if re.search(r"speed|math|quant", t): gaps.append("Banking Speed Maths & Data Interpretation")
        if re.search(r"awareness|economy|affairs|rbi", t): gaps.append("Banking & Financial Awareness Monthly Digests")
        if not gaps: gaps.append("Banking Prelims & Mains Full Mocks")

    elif cat in ("JEE", "NEET"):
        if re.search(r"physics|formula", t): gaps.append("JEE/NEET Physics Formulas & Problem Solving")
        if re.search(r"bio|biology|botany|zoology", t): gaps.append("NEET NCERT Line-by-Line Biology Notes")
        if re.search(r"chem|chemistry", t): gaps.append("JEE/NEET Organic & Inorganic Chemistry Notes")
        if not gaps: gaps.append("NTA JEE/NEET Chapterwise Question Banks")

    elif cat in ("NCERT", "BOARD_10_12"):
        if re.search(r"12th|hsc|science", t): gaps.append("Maharashtra 12th HSC Board Science Compendiums")
        if re.search(r"10th|ssc", t): gaps.append("Maharashtra 10th SSC Board Question Sets")
        if re.search(r"ncert|cbse|old", t): gaps.append("NCERT Class 6 - 12 Standard Textbook Sets")
        if not gaps: gaps.append("State Board & Balbharati Master Solution Guides")

    elif cat == "UPSC":
        if re.search(r"hindi|साहित्य", t): gaps.append("UPSC Hindi Medium Standard Study Notes")
        if re.search(r"topper|strategy", t): gaps.append("UPSC CSE Topper Answer Copies & Strategy")
        if not gaps: gaps.append("UPSC General Studies GS 1-4 Compilations")

    return gaps


def compute_recommended_backfill(score: float, yield_pct: float) -> int:
    """Recommend optimal batch size based on composite audit score and PDF density."""
    if score >= 85 and yield_pct >= 60:
        return 150
    elif score >= 70 or yield_pct >= 40:
        return 100
    elif score >= 55:
        return 75
    else:
        return 50


async def main():
    await init_db()
    with open("data/discovered_channels.json", encoding="utf-8") as f:
        raw_channels = json.load(f)

    print("=" * 135)
    print(" 📡 SECOND-STAGE TELEGRAM SOURCE AUDIT & MULTI-FACTOR RANKING")
    print(f" 📅 Timestamp: {NOW_DATE.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(" 🔒 Status: PENDING_REVIEW (No downloads, no redistribution)")
    print("=" * 135 + "\n")

    all_titles = [c.get("title", "") for c in raw_channels]

    audited_channels = []
    removed_stale_channels = []

    for ch in raw_channels:
        total_score, breakdown, is_valid, reason = calculate_channel_scores(ch, all_titles)
        if not is_valid:
            removed_stale_channels.append({
                "username": ch["username"],
                "title": ch["title"],
                "category": ch["category"],
                "latest_date": ch.get("latest_date", "N/A"),
                "reason": reason,
            })
            continue

        gaps = map_coverage_gaps(ch["category"], ch["title"], ch["username"])
        rec_backfill = compute_recommended_backfill(total_score, ch["pdf_yield_pct"])

        audited_channels.append({
            **ch,
            "composite_score": total_score,
            "score_breakdown": breakdown,
            "coverage_gaps": gaps,
            "recommended_backfill": rec_backfill,
            "audit_status": ChannelAuthStatus.PENDING_REVIEW.value,
        })

    # Sort audited channels by composite_score desc
    audited_channels.sort(key=lambda x: x["composite_score"], reverse=True)

    # Save to json
    out_file = Path("data/second_stage_audit_ranked.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(audited_channels, f, ensure_ascii=False, indent=2)

    print(f"✅ Active Verified Channels Retained : {len(audited_channels)}")
    print(f"❌ Stale/Inactive Channels Removed   : {len(removed_stale_channels)} (no activity in > 180 days)\n")

    print("=" * 135)
    print(" 📊 STALE / INACTIVE CHANNELS FILTERED OUT (< 180 Days Active)")
    print("=" * 135)
    for idx, rem in enumerate(removed_stale_channels, 1):
        print(f" {idx:2d}. {rem['username']:<32} | #{rem['category']:<12} | Latest: {rem['latest_date']:<10} | Reason: {rem['reason']}")

    print("\n" + "=" * 135)
    print(" 🏆 TOP 50 DISCOVERED CHANNELS OVERALL (RANKED BY COMPOSITE QUALITY SCORE)")
    print("=" * 135)
    print(f"{'#':<3} | {'USERNAME':<32} | {'CAT':<12} | {'SCORE':<6} | {'ACT(30)':<7} | {'YLD(30)':<7} | {'EDU(25)':<7} | {'DIV(15)':<7} | {'PDFS/100':<8} | {'YIELD %':<7} | {'REC BACKFILL':<12} | {'LATEST':<10}")
    print("─" * 135)

    for idx, c in enumerate(audited_channels[:50], 1):
        b = c["score_breakdown"]
        print(f"{idx:2d}. | {c['username']:<32} | #{c['category']:<11} | {c['composite_score']:<6.1f} | {b['activity']:<7.1f} | {b['yield']:<7.1f} | {b['usefulness']:<7.1f} | {b['diversity']:<7.1f} | {c['pdf_count_sample']:<8} | {c['pdf_yield_pct']:<7.1f} | {c['recommended_backfill']:<12} | {c['latest_date']:<10}")

    print("─" * 135)

    # Group by category (Top 5 - 10 per exam)
    by_cat = {}
    for c in audited_channels:
        by_cat.setdefault(c["category"], []).append(c)

    print("\n" + "=" * 135)
    print(" 🏛️ TOP CHANNELS PER EXAM CATEGORY (Capped 5–10 Best Sources)")
    print("=" * 135)

    category_order = [
        "MPSC", "POLICE_BHARTI", "SARAL_SEVA", "SSC", "BANKING",
        "UPSC", "JEE", "NEET", "NCERT", "BOARD_10_12"
    ]

    for cat in category_order:
        items = by_cat.get(cat, [])
        if not items:
            continue
        print(f"\n📁 Exam Category: #{cat} (Top {min(10, len(items))} Vetted Sources)")
        print(f"{'Rank':<4} | {'USERNAME':<32} | {'SCORE':<6} | {'PDFS/100':<8} | {'YIELD %':<7} | {'REC BACKFILL':<12} | {'TARGET COVERAGE GAP':<40} | {'TITLE'}")
        print("─" * 135)
        for r_idx, c in enumerate(items[:10], 1):
            gap_str = c["coverage_gaps"][0] if c["coverage_gaps"] else "General Subject Prep"
            print(f"{r_idx:2d}.   | {c['username']:<32} | {c['composite_score']:<6.1f} | {c['pdf_count_sample']:<8} | {c['pdf_yield_pct']:<7.1f} | {c['recommended_backfill']:<12} | {gap_str:<40} | {c['title'][:30]}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
