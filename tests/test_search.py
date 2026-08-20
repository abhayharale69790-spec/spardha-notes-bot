"""Unit Tests for RapidFuzz Bilingual Search and Transliterations."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base, ExamCategory, MaterialType
from database import crud


@pytest_asyncio.fixture
async def search_db_session():
    """Isolated in-memory SQLite async database populated with bilingual test materials."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        # Seed test documents with English and Marathi terms
        await crud.create_study_material(
            session=session,
            title="MPSC भारतीय राज्यघटना व राज्यशास्त्र संपूर्ण मार्गदर्शक",
            exam_category=ExamCategory.MPSC,
            subject="राज्यशास्त्र",
            material_type=MaterialType.SHORT_NOTES,
            file_path="https://example.com/polity_marathi.pdf",
            year=2024,
        )
        await crud.create_study_material(
            session=session,
            title="Indian Polity and Constitution for Civil Services Prelims",
            exam_category=ExamCategory.MPSC,
            subject="Polity",
            material_type=MaterialType.SHORT_NOTES,
            file_path="https://example.com/polity_english.pdf",
            year=2023,
        )
        await crud.create_study_material(
            session=session,
            title="आधुनिक भारताचा इतिहास व महाराष्ट्राचा विशेष संदर्भ",
            exam_category=ExamCategory.MPSC,
            subject="इतिहास",
            material_type=MaterialType.PYQ,
            file_path="https://example.com/history_marathi.pdf",
            year=2022,
        )
        await crud.create_study_material(
            session=session,
            title="Maharashtra Police Bharti Ankganit va Buddhimatta Sarav Paper",
            exam_category=ExamCategory.POLICE_BHARTI,
            subject="गणित व बुद्धिमत्ता",
            material_type=MaterialType.TEST_PAPER,
            file_path="https://example.com/police_maths.pdf",
            year=2024,
        )

        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_transliteration_polity_returns_marathi(search_db_session: AsyncSession):
    """Searching for 'Polity' should return both English and Marathi 'राज्यशास्त्र' materials."""
    results = await crud.search_study_materials(search_db_session, query="Polity")
    assert len(results) >= 2
    titles = [r.title for r in results]
    assert any("राज्यशास्त्र" in t for t in titles)
    assert any("Polity" in t for t in titles)


@pytest.mark.asyncio
async def test_transliteration_rajyashastra_returns_polity(search_db_session: AsyncSession):
    """Searching for transliterated 'Rajyashastra' should find 'राज्यशास्त्र' and 'Polity'."""
    results = await crud.search_study_materials(search_db_session, query="Rajyashastra")
    assert len(results) >= 1
    assert any("राज्यशास्त्र" in r.title or "Polity" in r.title for r in results)


@pytest.mark.asyncio
async def test_fuzzy_typo_resilience(search_db_session: AsyncSession):
    """Minor spelling mistakes (e.g. 'Itihas' or 'Itihaas') should match 'इतिहास'."""
    results = await crud.search_study_materials(search_db_session, query="Itihas")
    assert len(results) >= 1
    assert any("इतिहास" in r.title for r in results)


@pytest.mark.asyncio
async def test_marathi_maths_synonyms(search_db_session: AsyncSession):
    """Searching for 'Maths' or 'Ganit' should return 'गणित व बुद्धिमत्ता'."""
    results_maths = await crud.search_study_materials(search_db_session, query="Maths")
    assert len(results_maths) >= 1
    assert any("Ankganit" in r.title or "गणित" in r.subject for r in results_maths)

    results_ganit = await crud.search_study_materials(search_db_session, query="गणित")
    assert len(results_ganit) >= 1


@pytest.mark.asyncio
async def test_conversational_student_query_cleaning(search_db_session: AsyncSession):
    """Conversational phrases like 'मला गणिताचे नोट्स पाहिजेत' should return maths materials."""
    from bot.handlers.search import clean_student_conversational_query
    raw_prompt = "मला गणिताचे नोट्स पाहिजेत"
    cleaned = clean_student_conversational_query(raw_prompt)
    assert "पाहिजेत" not in cleaned
    assert "मला" not in cleaned
    results = await crud.search_study_materials(search_db_session, query=cleaned)
    assert len(results) >= 1

