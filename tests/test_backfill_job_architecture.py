"""Unit tests for Detached Resumable Backfill Job Architecture."""

import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from database.models import (
    Base,
    BackfillJobStatus,
    BackfillTaskStatus,
    ChannelAuthStatus,
    ExamCategory,
)
from database import crud
from scripts.backfill_control import is_pid_running


@pytest_asyncio.fixture
async def test_session():
    """Create an isolated in-memory SQLite database session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_backfill_job_lifecycle(test_session: AsyncSession):
    """Test full creation, task distribution, checkpointing, and completion of a backfill job."""
    # 1. Register test channels
    ch1 = await crud.get_or_create_telegram_channel(
        session=test_session,
        channel_id=-10099901,
        channel_username="test_mpsc_channel",
        title="Test MPSC Channel",
        exam_category=ExamCategory.MPSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    )
    ch2 = await crud.get_or_create_telegram_channel(
        session=test_session,
        channel_id=-10099902,
        channel_username="test_police_channel",
        title="Test Police Channel",
        exam_category=ExamCategory.POLICE_BHARTI,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    )

    # 2. Create Job
    job = await crud.create_backfill_job(
        session=test_session,
        job_uuid="test_job_12345",
        total_channels=2,
        config_json='{"limit": 50}',
        worker_pid=99999,
    )
    assert job.id is not None
    assert job.job_uuid == "test_job_12345"
    assert job.status == BackfillJobStatus.RUNNING

    # 3. Create Tasks
    tasks = await crud.create_backfill_channel_tasks(
        session=test_session,
        job_id=job.id,
        channels=[ch1, ch2],
    )
    assert len(tasks) == 2
    assert tasks[0].status == BackfillTaskStatus.PENDING

    # 4. Fetch Next Pending Task
    next_task = await crud.get_next_pending_backfill_task(test_session, job.id)
    assert next_task is not None
    assert next_task.id == tasks[0].id

    # 5. Checkpoint Progress
    updated_task = await crud.update_backfill_task_progress(
        session=test_session,
        task_id=next_task.id,
        last_successful_msg_id=150,
        scanned_delta=10,
        ingested_delta=2,
    )
    assert updated_task.last_successful_msg_id == 150
    assert updated_task.status == BackfillTaskStatus.IN_PROGRESS

    # 6. Complete Task
    completed_task = await crud.complete_backfill_task(
        session=test_session,
        task_id=next_task.id,
        scanned_total=50,
        ingested_total=5,
    )
    assert completed_task.status == BackfillTaskStatus.COMPLETED

    # 7. Check Next Task is ch2
    next_task_2 = await crud.get_next_pending_backfill_task(test_session, job.id)
    assert next_task_2 is not None
    assert next_task_2.channel_id == ch2.channel_id


def test_pid_liveness_check():
    """Verify PID liveness check correctly identifies current process."""
    current_pid = os.getpid()
    assert is_pid_running(current_pid) is True
    assert is_pid_running(9999999) is False
