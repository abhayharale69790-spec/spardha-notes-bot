import asyncio
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.session import init_db, get_session
from database.models import BackfillJob, BackfillChannelTask, BackfillTaskStatus
from sqlalchemy import select, update

async def sync():
    await init_db()
    async with get_session() as s:
        job_res = await s.execute(select(BackfillJob).order_by(BackfillJob.id.desc()).limit(1))
        job = job_res.scalar_one_or_none()
        if not job:
            return
        task_res = await s.execute(
            select(BackfillChannelTask).where(
                BackfillChannelTask.job_id == job.id,
                BackfillChannelTask.status.in_([BackfillTaskStatus.PENDING, BackfillTaskStatus.IN_PROGRESS, BackfillTaskStatus.COMPLETED]),
            )
        )
        active_tasks = task_res.scalars().all()
        job.total_channels = len(active_tasks)
        s.add(job)
        await s.commit()
        print(f"Synced Job #{job.id} total_channels = {job.total_channels}")

if __name__ == "__main__":
    asyncio.run(sync())
