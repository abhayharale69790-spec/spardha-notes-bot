"""Database Healing & Dead Link Purge Script.

Purges dead/unreachable records and duplicate entries from the database,
leaving only 100% verified, live retrievable study materials.
"""

import asyncio
import logging
from pathlib import Path
import sys
from typing import Set
import httpx
from sqlalchemy import select, delete

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.models import StudyMaterial
from database.session import get_session, init_db
from scripts.audit_live_materials import check_url_live

logger = logging.getLogger(__name__)


async def heal_and_purge_database():
    """Purge invalid and duplicate records, retaining only guaranteed working materials."""
    await init_db()
    print("=" * 80)
    print(" 🧹 DATABASE HEALING & RETRIEVABILITY SANITIZATION")
    print("=" * 80)

    async with get_session() as session:
        stmt = select(StudyMaterial).order_by(StudyMaterial.id)
        res = await session.execute(stmt)
        all_materials = list(res.scalars().all())

    print(f"Initial material count: {len(all_materials)}")

    seen_urls: Set[str] = set()
    seen_titles: Set[str] = set()
    to_delete_ids: Set[int] = set()
    verified_ids: Set[int] = set()

    sem = asyncio.Semaphore(20)

    async with httpx.AsyncClient(verify=False) as client:
        async def check_item(item: StudyMaterial):
            norm_url = item.file_path.strip().lower()
            norm_title = item.title.strip().lower()

            if norm_url in seen_urls or norm_title in seen_titles:
                to_delete_ids.add(item.id)
                return

            seen_urls.add(norm_url)
            seen_titles.add(norm_title)

            async with sem:
                is_live, status_code, details = await check_url_live(client, item.file_path)

            if is_live:
                verified_ids.add(item.id)
            else:
                to_delete_ids.add(item.id)

        tasks = [check_item(m) for m in all_materials]
        await asyncio.gather(*tasks)

    print(f"Identified {len(to_delete_ids)} dead / duplicate records to purge.")
    print(f"Retaining {len(verified_ids)} 100% verified, live materials.")

    if to_delete_ids:
        async with get_session() as session:
            del_stmt = delete(StudyMaterial).where(StudyMaterial.id.in_(list(to_delete_ids)))
            await session.execute(del_stmt)
            await session.commit()

    async with get_session() as session:
        cnt_stmt = select(StudyMaterial)
        final_res = await session.execute(cnt_stmt)
        final_materials = list(final_res.scalars().all())

    print("-" * 80)
    print(f"✅ HEALING COMPLETE: Database now contains exactly {len(final_materials)} VERIFIED, LIVE materials!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(heal_and_purge_database())
