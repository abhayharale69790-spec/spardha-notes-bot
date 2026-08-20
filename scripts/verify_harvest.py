"""Live Harvest Verification Query Script."""

import asyncio
from pathlib import Path
import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.session import get_session
from database import crud


async def main():
    async with get_session() as session:
        test_queries = [
            "NCERT Class 10 Science Marathi",
            "10th SSC Algebra Question Bank",
            "12th HSC Physics Model Paper",
            "JEE Main 2023 Solved Paper",
            "NEET Biology Human Physiology",
            "UPSC Prelims GS 2022",
            "MPSC Combine Group B 2023",
            "मुंबई पोलीस भरती",
            "तलाठी TCS पॅटर्न",
            "Banking Speed Maths",
            "SSC CGL Advanced Maths",
            "शासन निर्णय वयोमर्यादा",
        ]

        print("=== 525+ MULTI-SOURCE HARVEST SEARCH VERIFICATION ===")
        for q in test_queries:
            results = await crud.search_study_materials(session, query=q, limit=1)
            if results:
                r = results[0]
                print(f"✅ Query: '{q}'\n   └─ [{r.exam_category.value}] {r.title[:75]}... ({r.year})\n")
            else:
                print(f"⚠️ Query: '{q}' -> No match found\n")


if __name__ == "__main__":
    asyncio.run(main())
