"""Script to execute MTProto Study Channel Discovery and generate the Top 50 Grouped Report."""

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

from config.settings import get_settings
from database.session import init_db
from collectors.telegram_channel_discovery import telegram_channel_discovery

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main():
    await init_db()
    print("=" * 135)
    print(" 📡 EXECUTING AUTOMATIC TELEGRAM STUDY-CHANNEL DISCOVERY")
    print(f" 📅 Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(" 🔒 Mode: Discovery Only (Metadata Inspection, NO downloads, NO republishing)")
    print("=" * 135 + "\n")

    discovered = await telegram_channel_discovery.discover_channels(limit_per_keyword=20)
    print(f"\n✅ Total Discovered Channels Audited: {len(discovered)}")

    # Sort by pdf_count_sample desc, pdf_yield_pct desc
    discovered.sort(key=lambda x: (x["pdf_count_sample"], x["pdf_yield_pct"]), reverse=True)
    top_50 = discovered[:50]

    # Group by Category
    by_category = {}
    for ch in top_50:
        cat = ch["category"]
        by_category.setdefault(cat, []).append(ch)

    print("\n" + "=" * 135)
    print(" 🏆 TOP 50 NEW DISCOVERED CHANNELS GROUPED BY EXAM CATEGORY")
    print("=" * 135)

    category_order = [
        "MPSC", "POLICE_BHARTI", "SARAL_SEVA", "SSC", "BANKING",
        "UPSC", "JEE", "NEET", "NCERT", "BOARD_10_12", "GENERAL"
    ]

    channel_counter = 1
    for cat in category_order:
        items = by_category.get(cat, [])
        if not items:
            continue
        
        print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f" 🏛️ CATEGORY: #{cat} ({len(items)} High-Value Channels Discovered)")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"{'#':<3} | {'USERNAME':<30} | {'ACC':<3} | {'HIST':<4} | {'PDFS/100':<8} | {'YIELD %':<7} | {'EST. YIELD':<16} | {'LATEST (DATE)':<20} | {'RELATED':<22} | {'TITLE'}")
        print("─" * 135)

        for item in items:
            latest_str = f"#{item['latest_msg_id']} ({item['latest_date']})" if item['latest_msg_id'] != 'N/A' else 'N/A'
            related_short = item['related_channel'][:20] + "..." if len(item['related_channel']) > 20 else item['related_channel']
            print(f"{channel_counter:2d}. | {item['username']:<30} | {item['accessible']:<3} | {item['historical_access']:<4} | {item['pdf_count_sample']:<8} | {item['pdf_yield_pct']:<7} | {item['estimated_yield']:<16} | {latest_str:<20} | {related_short:<22} | {item['title'][:35]}")
            channel_counter += 1

    print("\n" + "=" * 135)
    print(f" 🎉 COMPLETED DISCOVERY OF TOP {len(top_50)} NEW STUDY CHANNELS")
    print(" 🔒 Database Status: Stored as ChannelAuthStatus.PENDING_REVIEW (is_active=False)")
    print("=" * 135 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
