"""Asynchronous CRUD Operations with RapidFuzz Bilingual Search."""

from typing import List, Optional, Sequence, Dict
from rapidfuzz import fuzz, process
from sqlalchemy import distinct, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import (
    ExamCategory,
    MaterialType,
    StagingQueue,
    StagingStatus,
    StudyMaterial,
)

SYNONYM_CLUSTERS: List[List[str]] = [
    ["polity", "rajyashastra", "rajyashashtra", "राज्यशास्त्र", "राज्यघटना", "संविधान", "constitution", "governance"],
    ["history", "itihas", "itihaas", "इतिहास", "आधुनिक भारत", "महाराष्ट्र इतिहास", "modern history"],
    ["geography", "bhugol", "भूगोल", "महाराष्ट्र भूगोल"],
    ["economics", "arthashastra", "अर्थशास्त्र", "अर्थव्यवस्था", "economy"],
    ["science", "vigyan", "vidnyan", "विज्ञान", "सामान्य विज्ञान"],
    ["maths", "mathematics", "ganit", "गणित", "अंकगणित", "aptitude", "quantitative", "ankganit"],
    ["reasoning", "buddhimatta", "बुद्धिमत्ता", "तर्कशक्ती", "logical"],
    ["marathi", "marathi vyakaran", "मराठी", "मराठी व्याकरण", "व्याकरण"],
    ["english", "english grammar", "इंग्रजी", "इंग्रजी व्याकरण"],
    ["current affairs", "chalu ghadamodi", "चालू घडामोडी", "घडामोडी"],
    ["gr", "shasan nirnay", "शासन निर्णय", "परिपत्रक", "resolution", "शुद्धीपत्रक"],
    ["pyq", "question paper", "prashnapatrika", "प्रश्नपत्रिका", "उत्तरतालिका", "answer key"],
    ["syllabus", "abhyaskram", "अभ्यासक्रम", "pattern"],
    ["police", "police bharti", "पोलीस", "पोलीस भरती", "khaki"],
    ["talathi", "तलाठी", "saral seva", "सरळ सेवा", "zp", "जिल्हा परिषद"],
    ["rajyaseva", "राज्यसेवा", "combine", "संयुक्त पूर्व"],
]


def expand_bilingual_terms(query: str) -> List[str]:
    """Expand query terms using bidirectional synonym & transliteration clusters."""
    query_clean = query.strip().lower()
    terms = [query_clean]
    words = query_clean.split()

    for cluster in SYNONYM_CLUSTERS:
        matched = False
        # Direct phrase or word match
        for item in cluster:
            if item in query_clean:
                matched = True
                break

        if not matched:
            # Word-by-word fuzzy match
            for w in words:
                for item in cluster:
                    if w == item or (len(w) >= 4 and fuzz.ratio(w, item) >= 80):
                        matched = True
                        break
                if matched:
                    break

        if matched:
            for item in cluster:
                if item not in terms:
                    terms.append(item)

    return terms


# ==============================================================================
# StudyMaterial CRUD
# ==============================================================================

async def create_study_material(
    session: AsyncSession,
    title: str,
    exam_category: ExamCategory,
    subject: str,
    material_type: MaterialType,
    file_path: str,
    year: Optional[int] = None,
    telegram_file_id: Optional[str] = None,
) -> StudyMaterial:
    """Create and persist a new study material record."""
    material = StudyMaterial(
        title=title.strip(),
        exam_category=exam_category,
        subject=subject.strip(),
        material_type=material_type,
        file_path=file_path.strip(),
        year=year,
        telegram_file_id=telegram_file_id,
    )
    session.add(material)
    await session.flush()
    await session.refresh(material)
    return material


async def get_study_material_by_id(
    session: AsyncSession,
    material_id: int,
) -> Optional[StudyMaterial]:
    """Retrieve a single study material by ID."""
    stmt = select(StudyMaterial).where(StudyMaterial.id == material_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_material_telegram_file_id(
    session: AsyncSession,
    material_id: int,
    telegram_file_id: str,
) -> Optional[StudyMaterial]:
    """Update and cache Telegram file_id for zero-bandwidth future document delivery."""
    stmt = (
        update(StudyMaterial)
        .where(StudyMaterial.id == material_id)
        .values(telegram_file_id=telegram_file_id)
        .returning(StudyMaterial)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def search_study_materials(
    session: AsyncSession,
    query: Optional[str] = None,
    exam_category: Optional[ExamCategory] = None,
    subject: Optional[str] = None,
    material_type: Optional[MaterialType] = None,
    year: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
) -> Sequence[StudyMaterial]:
    """Search study materials with RapidFuzz scoring and bilingual transliterations."""
    if not query:
        # Standard filter query without text scoring
        stmt = select(StudyMaterial)
        if exam_category:
            stmt = stmt.where(StudyMaterial.exam_category == exam_category)
        if subject:
            stmt = stmt.where(StudyMaterial.subject.ilike(f"%{subject}%"))
        if material_type:
            stmt = stmt.where(StudyMaterial.material_type == material_type)
        if year:
            stmt = stmt.where(StudyMaterial.year == year)

        stmt = stmt.order_by(StudyMaterial.created_at.desc()).offset(offset).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()

    # 1. Expand query terms
    expanded_terms = expand_bilingual_terms(query)

    # 2. Fetch candidates from DB matching any expanded term
    conditions = []
    for term in expanded_terms:
        pattern = f"%{term}%"
        conditions.append(StudyMaterial.title.ilike(pattern))
        conditions.append(StudyMaterial.subject.ilike(pattern))

    stmt = select(StudyMaterial)
    if conditions:
        stmt = stmt.where(or_(*conditions))

    if exam_category:
        stmt = stmt.where(StudyMaterial.exam_category == exam_category)
    if subject:
        stmt = stmt.where(StudyMaterial.subject.ilike(f"%{subject}%"))
    if material_type:
        stmt = stmt.where(StudyMaterial.material_type == material_type)
    if year:
        stmt = stmt.where(StudyMaterial.year == year)

    # Fetch broader pool for fuzzy ranking
    stmt = stmt.limit(100)
    result = await session.execute(stmt)
    candidates = list(result.scalars().all())

    # If DB ilike gave 0 results (e.g. typos like 'rajyashashtra' or 'politi'), fetch latest 100 in category
    if not candidates:
        fallback_stmt = select(StudyMaterial)
        if exam_category:
            fallback_stmt = fallback_stmt.where(StudyMaterial.exam_category == exam_category)
        fallback_stmt = fallback_stmt.order_by(StudyMaterial.created_at.desc()).limit(100)
        res_fb = await session.execute(fallback_stmt)
        candidates = list(res_fb.scalars().all())

    if not candidates:
        return []

    # 3. RapidFuzz Scoring across candidate titles and subjects
    scored_items = []
    query_clean = query.strip()

    for item in candidates:
        target_text = f"{item.title} {item.subject} {item.exam_category.value}"
        # Compute best token set and partial ratio
        score_direct = fuzz.token_set_ratio(query_clean, target_text)
        score_partial = fuzz.partial_ratio(query_clean, target_text)

        # Check against expanded synonym terms
        max_syn_score = 0
        for syn in expanded_terms[:6]:
            s_score = fuzz.token_set_ratio(syn, target_text)
            if s_score > max_syn_score:
                max_syn_score = s_score

        final_score = max(score_direct, score_partial, max_syn_score)

        if final_score >= 45:  # Relevance threshold
            scored_items.append((final_score, item))

    # Sort descending by RapidFuzz score
    scored_items.sort(key=lambda x: x[0], reverse=True)

    # Apply offset and limit
    ranked = [item for _, item in scored_items]
    return ranked[offset : offset + limit]


async def get_distinct_subjects_by_category(
    session: AsyncSession,
    exam_category: ExamCategory,
) -> List[str]:
    """Fetch all unique subjects available under an exam category."""
    stmt = (
        select(distinct(StudyMaterial.subject))
        .where(StudyMaterial.exam_category == exam_category)
        .order_by(StudyMaterial.subject)
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.all() if row[0]]


async def get_distinct_years_by_category_and_subject(
    session: AsyncSession,
    exam_category: ExamCategory,
    subject: str,
) -> List[int]:
    """Fetch all available years for an exam category and subject."""
    stmt = (
        select(distinct(StudyMaterial.year))
        .where(
            StudyMaterial.exam_category == exam_category,
            StudyMaterial.subject == subject,
            StudyMaterial.year.is_not(None),
        )
        .order_by(StudyMaterial.year.desc())
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.all() if row[0] is not None]


async def get_materials_by_type_or_category(
    session: AsyncSession,
    material_type: Optional[MaterialType] = None,
    exam_category: Optional[ExamCategory] = None,
    limit: int = 20,
    offset: int = 0,
) -> Sequence[StudyMaterial]:
    """List materials filtered by material type or category (e.g. for GR/PYQ feeds)."""
    stmt = select(StudyMaterial)
    if material_type:
        stmt = stmt.where(StudyMaterial.material_type == material_type)
    if exam_category:
        stmt = stmt.where(StudyMaterial.exam_category == exam_category)
    stmt = stmt.order_by(StudyMaterial.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


# ==============================================================================
# StagingQueue CRUD
# ==============================================================================

async def is_url_already_known(
    session: AsyncSession,
    source_url: str,
    pdf_url: Optional[str] = None,
) -> bool:
    """Check if URL has already been processed in staging queue or study materials."""
    staging_stmt = select(StagingQueue.id).where(
        or_(
            StagingQueue.source_url == source_url,
            StagingQueue.pdf_url == (pdf_url or source_url),
        )
    )
    staging_res = await session.execute(staging_stmt)
    if staging_res.first() is not None:
        return True

    material_stmt = select(StudyMaterial.id).where(
        StudyMaterial.file_path == (pdf_url or source_url)
    )
    material_res = await session.execute(material_stmt)
    return material_res.first() is not None


async def add_to_staging_queue(
    session: AsyncSession,
    title: str,
    source_url: str,
    pdf_url: str,
    extracted_summary: str,
    exam_category: ExamCategory = ExamCategory.GENERAL,
    subject: str = "General",
    material_type: MaterialType = MaterialType.GR,
    year: Optional[int] = None,
) -> StagingQueue:
    """Insert a newly scraped item into the admin staging queue."""
    item = StagingQueue(
        title=title.strip(),
        source_url=source_url.strip(),
        pdf_url=pdf_url.strip(),
        extracted_summary=extracted_summary.strip(),
        exam_category=exam_category,
        subject=subject.strip(),
        material_type=material_type,
        year=year,
        status=StagingStatus.PENDING,
    )
    session.add(item)
    await session.flush()
    await session.refresh(item)
    return item


async def get_staging_item_by_id(
    session: AsyncSession,
    item_id: int,
) -> Optional[StagingQueue]:
    """Retrieve staging queue item by ID."""
    stmt = select(StagingQueue).where(StagingQueue.id == item_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_staging_status(
    session: AsyncSession,
    item_id: int,
    status: StagingStatus,
    staging_message_id: Optional[int] = None,
) -> Optional[StagingQueue]:
    """Update staging status (APPROVED/REJECTED) and optionally link staging message ID."""
    values = {"status": status}
    if staging_message_id is not None:
        values["staging_message_id"] = staging_message_id

    stmt = (
        update(StagingQueue)
        .where(StagingQueue.id == item_id)
        .values(**values)
        .returning(StagingQueue)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_pending_staging_items(
    session: AsyncSession,
    limit: int = 50,
) -> Sequence[StagingQueue]:
    """Retrieve pending staging drafts."""
    stmt = (
        select(StagingQueue)
        .where(StagingQueue.status == StagingStatus.PENDING)
        .order_by(StagingQueue.created_at.asc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.scalars().all()
