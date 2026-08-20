"""Run live syllabus coverage audit and autonomous gap remediation."""

import asyncio
from datetime import datetime, timezone
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.session import init_db
from services.coverage_engine import coverage_engine
from services.gap_detector import gap_detector
from services.coverage_report import generate_console_coverage_report


async def main():
    await init_db()

    print("\n🔍 1. Evaluating Live Database against Official Exam Syllabi...")
    initial_matrix = await coverage_engine.compute_coverage_matrix()
    print(generate_console_coverage_report(initial_matrix))

    print("\n🎯 2. Executing Autonomous Gap Detection & Remediation Cycle...")
    res = await gap_detector.run_autonomous_remediation_cycle(max_remediations=10)
    print(f"   ✨ Remediated {res['remediations_completed']} gaps.")
    print(f"   📈 Coverage improved: {res['initial_coverage_pct']}% -> {res['final_coverage_pct']}%")

    print("\n📊 3. Post-Remediation Recheck Coverage Dashboard:")
    final_matrix = res["matrix"]
    print(generate_console_coverage_report(final_matrix))


if __name__ == "__main__":
    asyncio.run(main())
