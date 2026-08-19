"""Unit Tests for Database Models and Asynchronous CRUD Operations."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import (
    Base,
    ExamCategory,
    MaterialType,
    StagingStatus,
    StudyMaterial,
    StagingQueue,
)
from database import crud


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
async def test_create_and_get_study_material(test_session: AsyncSession):
    """Test inserting and retrieving a StudyMaterial entity."""
    material = await crud.create_study_material(
        session=test_session,
        title="MPSC Rajyaseva Prelims 2023 GS Paper 1",
        exam_category=ExamCategory.MPSC,
        subject="General Studies",
        material_type=MaterialType.PYQ,
        file_path="https://mpsc.gov.in/files/rajyaseva2023.pdf",
        year=2023,
    )
    assert material.id is not None
    assert material.title == "MPSC Rajyaseva Prelims 2023 GS Paper 1"
    assert material.exam_category == ExamCategory.MPSC
    assert material.material_type == MaterialType.PYQ
    assert material.year == 2023
    assert material.telegram_file_id is None

    # Retrieve by ID
    fetched = await crud.get_study_material_by_id(test_session, material.id)
    assert fetched is not None
    assert fetched.id == material.id


@pytest.mark.asyncio
async def test_update_telegram_file_id(test_session: AsyncSession):
    """Test caching Telegram file ID."""
    material = await crud.create_study_material(
        session=test_session,
        title="Maharashtra Police Bharti Model Paper",
        exam_category=ExamCategory.POLICE_BHARTI,
        subject="Mathematics",
        material_type=MaterialType.TEST_PAPER,
        file_path="https://mahapolice.gov.in/paper.pdf",
        year=2024,
    )

    updated = await crud.update_material_telegram_file_id(
        session=test_session,
        material_id=material.id,
        telegram_file_id="BAACAgUAAxkBAAI_FILE_ID_12345",
    )
    assert updated is not None
    assert updated.telegram_file_id == "BAACAgUAAxkBAAI_FILE_ID_12345"


@pytest.mark.asyncio
async def test_search_and_filters(test_session: AsyncSession):
    """Test multi-criteria search and filter queries."""
    # Seed test materials
    await crud.create_study_material(
        session=test_session,
        title="Indian Polity Revision Notes",
        exam_category=ExamCategory.MPSC,
        subject="Polity",
        material_type=MaterialType.SHORT_NOTES,
        file_path="https://example.com/polity.pdf",
        year=2024,
    )
    await crud.create_study_material(
        session=test_session,
        title="Modern History of Maharashtra PYQ",
        exam_category=ExamCategory.MPSC,
        subject="History",
        material_type=MaterialType.PYQ,
        file_path="https://example.com/history.pdf",
        year=2022,
    )
    await crud.create_study_material(
        session=test_session,
        title="Banking Quantitative Aptitude Practice Set",
        exam_category=ExamCategory.BANKING,
        subject="Quantitative Aptitude",
        material_type=MaterialType.TEST_PAPER,
        file_path="https://example.com/banking.pdf",
        year=2024,
    )

    # 1. Keyword search
    res = await crud.search_study_materials(test_session, query="Polity")
    assert len(res) == 1
    assert "Polity" in res[0].title

    # 2. Category filter
    res_mpsc = await crud.search_study_materials(test_session, exam_category=ExamCategory.MPSC)
    assert len(res_mpsc) == 2

    # 3. Year filter
    res_2022 = await crud.search_study_materials(test_session, year=2022)
    assert len(res_2022) == 1
    assert res_2022[0].year == 2022

    # 4. Distinct subjects
    subjects = await crud.get_distinct_subjects_by_category(test_session, ExamCategory.MPSC)
    assert "History" in subjects
    assert "Polity" in subjects
    assert len(subjects) == 2


@pytest.mark.asyncio
async def test_staging_queue_workflow(test_session: AsyncSession):
    """Test staging queue insertion, duplicate checks, and status changes."""
    source_url = "https://mpsc.gov.in/notice/101"
    pdf_url = "https://mpsc.gov.in/files/notice101.pdf"

    # Verify not known yet
    is_known = await crud.is_url_already_known(test_session, source_url, pdf_url)
    assert is_known is False

    # Insert into staging
    staging_item = await crud.add_to_staging_queue(
        session=test_session,
        title="MPSC State Services 2024 Notification",
        source_url=source_url,
        pdf_url=pdf_url,
        extracted_summary="Notification for 2024 prelims",
        exam_category=ExamCategory.MPSC,
        subject="General",
        material_type=MaterialType.SYLLABUS,
        year=2024,
    )
    assert staging_item.id is not None
    assert staging_item.status == StagingStatus.PENDING

    # Verify duplicate detection
    is_known_after = await crud.is_url_already_known(test_session, source_url, pdf_url)
    assert is_known_after is True

    # Update status to APPROVED
    updated_item = await crud.update_staging_status(
        session=test_session,
        item_id=staging_item.id,
        status=StagingStatus.APPROVED,
        staging_message_id=9876,
    )
    assert updated_item is not None
    assert updated_item.status == StagingStatus.APPROVED
    assert updated_item.staging_message_id == 9876
