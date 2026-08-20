"""Unit Tests for Admin Dashboard Stats & Coverage Reports."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base, ExamCategory, MaterialType
from database import crud


@pytest_asyncio.fixture
async def stats_db_session():
    """Isolated in-memory SQLite async database for dashboard and coverage verification."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        # Seed test items across multiple exam categories
        await crud.create_study_material(
            session=session,
            title="MPSC State Services Notes",
            exam_category=ExamCategory.MPSC,
            subject="राज्यशास्त्र",
            material_type=MaterialType.SHORT_NOTES,
            file_path="https://example.com/mpsc.pdf",
            year=2024,
        )
        await crud.create_study_material(
            session=session,
            title="Police Bharti Maths Paper",
            exam_category=ExamCategory.POLICE_BHARTI,
            subject="गणित",
            material_type=MaterialType.TEST_PAPER,
            file_path="https://example.com/police.pdf",
            year=2024,
        )
        await crud.create_study_material(
            session=session,
            title="JEE Main Physics Compendium",
            exam_category=ExamCategory.JEE,
            subject="Physics",
            material_type=MaterialType.SHORT_NOTES,
            file_path="https://example.com/jee.pdf",
            year=2024,
        )

        # Record sample metric
        await crud.record_ingestion_metric(
            session=session,
            source_id="test_source",
            source_name="Test Source",
            files_scanned=10,
            files_downloaded=8,
            files_processed=8,
            duplicates_detected=2,
        )

        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_get_admin_dashboard_stats(stats_db_session: AsyncSession):
    """Verify aggregated admin telemetry stats."""
    stats = await crud.get_admin_dashboard_stats(stats_db_session)
    assert stats["total_verified"] == 3
    assert stats["files_scanned"] == 10
    assert stats["files_downloaded"] == 8
    assert stats["duplicates_detected"] == 2
    assert "MPSC" in stats["category_breakdown"]
    assert "POLICE_BHARTI" in stats["category_breakdown"]


@pytest.mark.asyncio
async def test_get_exam_coverage_summary(stats_db_session: AsyncSession):
    """Verify exam coverage breakdown."""
    coverage = await crud.get_exam_coverage_summary(stats_db_session)
    assert "MPSC" in coverage
    assert coverage["MPSC"]["राज्यशास्त्र"] == 1
    assert "POLICE_BHARTI" in coverage
    assert coverage["POLICE_BHARTI"]["गणित"] == 1
    assert "JEE" in coverage
