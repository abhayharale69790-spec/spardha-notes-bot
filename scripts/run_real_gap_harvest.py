"""Run Real Gap-Filling Harvester and Output Telemetry Report."""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from database.session import init_db
from services.coverage_engine import coverage_engine
from services.coverage_report import generate_console_coverage_report
from services.real_gap_harvester import real_gap_harvester



async def main():
    await init_db()

    print("\n" + "=" * 95)
    print(" 🚀 EXECUTING REAL GAP-FILLING HARVESTER")
    print(f" 📅 Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 95)

    # 1. Run harvest cycle
    report = await real_gap_harvester.run_gap_filling_harvest_cycle(max_materials_to_add=25)

    # 2. Print user requested summary metrics
    print("\n" + "=" * 95)
    print(" 📊 REAL GAP-FILLING HARVEST TELEMETRY REPORT:")
    print("=" * 95)
    print(f"  • Gaps Before            : {report.gaps_before}")
    print(f"  • Materials Added        : {report.materials_added}")
    print(f"  • Gaps Resolved          : {report.gaps_resolved}")
    print(f"  • Gaps Remaining         : {report.gaps_remaining}")
    print(f"  • Coverage Before / After: {report.coverage_before_pct}% ➔ {report.coverage_after_pct}%")
    print(f"  • Failed Sources         : {', '.join(report.failed_sources) if report.failed_sources else 'None'}")
    print(f"  • Exhausted Sources      : {', '.join(report.exhausted_sources) if report.exhausted_sources else 'None'}")
    print("=" * 95 + "\n")

    # 3. Print details of any newly added materials
    if report.added_materials_details:
        print("📄 Newly Added Real Verified Materials:")
        for idx, item in enumerate(report.added_materials_details, 1):
            print(f"  [{idx:02d}] ID #{item['id']} | [{item['exam_category']}] {item['title'][:55]}...")
            print(f"       Topic: {item['topic']} | Type: {item['material_type']} | Pages: {item['page_count']} | Msg ID: {item['telegram_msg_id']}")

    # 4. Display Post-Harvest Console Dashboard
    final_matrix = await coverage_engine.compute_coverage_matrix()
    print("\n" + generate_console_coverage_report(final_matrix))


if __name__ == "__main__":
    asyncio.run(main())
