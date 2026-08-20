"""Asynchronous CRUD Operations with Cloud-Native Hybrid Search."""

import re
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
from search_engine.hybrid_search import rank_hybrid_materials

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
    ["upsc", "civil services", "ias", "ips", "ifs", "csat"],
    ["jee", "jee main", "jee advanced", "engineering", "iit", "physics", "chemistry"],
    ["neet", "neet ug", "medical", "mbbs", "bds", "biology", "botany", "zoology"],
    ["board", "ssc 10th", "hsc 12th", "10th board", "12th board", "state board"],
    ["ncert", "cbse", "textbook", "foundation", "class 6", "class 10", "class 12"],
    ["banking", "ibps", "sbi", "rbi", "bank po", "bank clerk"],
    ["ssc", "cgl", "chsl", "staff selection", "mts", "ssc gd"],
]


def expand_bilingual_terms(query: Optional[str]) -> List[str]:
    """Expand query terms using bidirectional synonym & transliteration clusters."""
    if not query or not query.strip():
        return []

    query_clean = query.strip().lower()
    terms = [query_clean]
    words = re.findall(r"[\w\u0900-\u097F]+", query_clean)

    for cluster in SYNONYM_CLUSTERS:
        matched = False
        # Direct phrase match
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
    """Insert a new verified study material into the database."""
    material = StudyMaterial(
        title=title,
        exam_category=exam_category,
        subject=subject,
        material_type=material_type,
        year=year,
        file_path=file_path,
        telegram_file_id=telegram_file_id,
    )
    session.add(material)
    await session.commit()
    await session.refresh(material)
    return material


async def get_study_material_by_id(
    session: AsyncSession,
    material_id: int,
) -> Optional[StudyMaterial]:
    """Fetch single study material by primary key ID."""
    stmt = select(StudyMaterial).where(StudyMaterial.id == material_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_materials_by_type_or_category(
    session: AsyncSession,
    material_type: Optional[MaterialType] = None,
    exam_category: Optional[ExamCategory] = None,
    limit: int = 10,
    offset: int = 0,
) -> Sequence[StudyMaterial]:
    """Fetch materials filtered by type or exam category ordered by newest first."""
    stmt = select(StudyMaterial)
    if material_type:
        stmt = stmt.where(StudyMaterial.material_type == material_type)
    if exam_category:
        stmt = stmt.where(StudyMaterial.exam_category == exam_category)

    stmt = stmt.order_by(StudyMaterial.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


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
    """Search study materials with Hybrid RapidFuzz + AI Ranking."""
    query_clean = query.strip() if query else ""

    if not query_clean:
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
    expanded_terms = expand_bilingual_terms(query_clean)

    # 2. Fetch candidates from DB matching any expanded term
    conditions = []
    for term in expanded_terms:
        safe_term = term.replace("%", "").replace("_", "")
        if safe_term:
            pattern = f"%{safe_term}%"
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

    # Fetch broader pool for ranking
    stmt = stmt.limit(100)
    result = await session.execute(stmt)
    candidates = list(result.scalars().all())

    # Fallback to recent materials in category if ilike yields 0
    if not candidates:
        fallback_stmt = select(StudyMaterial)
        if exam_category:
            fallback_stmt = fallback_stmt.where(StudyMaterial.exam_category == exam_category)
        fallback_stmt = fallback_stmt.order_by(StudyMaterial.created_at.desc()).limit(100)
        res_fb = await session.execute(fallback_stmt)
        candidates = list(res_fb.scalars().all())

    if not candidates:
        return []

    # 3. Hybrid AI + RapidFuzz Reciprocal Rank Fusion
    ranked = await rank_hybrid_materials(
        query=query_clean,
        candidates=candidates,
        expanded_terms=expanded_terms,
    )

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


async def update_material_telegram_file_id(
    session: AsyncSession,
    material_id: int,
    telegram_file_id: str,
) -> Optional[StudyMaterial]:
    """Cache Telegram file_id for instant zero-bandwidth dispatches."""
    stmt = (
        update(StudyMaterial)
        .where(StudyMaterial.id == material_id)
        .values(telegram_file_id=telegram_file_id)
    )
    await session.execute(stmt)
    await session.commit()
    return await get_study_material_by_id(session, material_id)


from sqlalchemy import distinct, or_, select, update, func

# ==============================================================================
# Staging Queue Operations
# ==============================================================================

async def is_url_already_known(
    session: AsyncSession,
    source_url: str,
    pdf_url: str,
    title: Optional[str] = None,
) -> bool:
    """Check if document has already been processed or staged by URL or Title."""
    conditions_stg = [
        StagingQueue.pdf_url == pdf_url,
    ]
    if title and title.strip():
        clean_t = title.strip().lower()
        conditions_stg.append(func.lower(StagingQueue.title) == clean_t)

    stmt_stg = select(StagingQueue.id).where(or_(*conditions_stg))
    res_stg = await session.execute(stmt_stg)
    if res_stg.scalar_one_or_none():
        return True

    conditions_mat = [
        StudyMaterial.file_path == pdf_url,
    ]
    if title and title.strip():
        clean_t = title.strip().lower()
        conditions_mat.append(func.lower(StudyMaterial.title) == clean_t)

    stmt_mat = select(StudyMaterial.id).where(or_(*conditions_mat))
    res_mat = await session.execute(stmt_mat)
    return res_mat.scalar_one_or_none() is not None


async def create_staging_item(
    session: AsyncSession,
    title: str,
    source_url: str,
    pdf_url: str,
    extracted_summary: str,
    exam_category: ExamCategory = ExamCategory.GENERAL,
    subject: str = "General",
    material_type: MaterialType = MaterialType.GR,
    year: Optional[int] = None,
) -> Optional[StagingQueue]:
    """Create a new staging queue draft item for admin review."""
    if await is_url_already_known(session, source_url=source_url, pdf_url=pdf_url, title=title):
        return None


    item = StagingQueue(
        title=title,
        source_url=source_url,
        pdf_url=pdf_url,
        extracted_summary=extracted_summary,
        exam_category=exam_category,
        subject=subject,
        material_type=material_type,
        year=year,
        status=StagingStatus.PENDING,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


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
    """Add a draft item to the staging queue (creates if not exists)."""
    item = await create_staging_item(
        session=session,
        title=title,
        source_url=source_url,
        pdf_url=pdf_url,
        extracted_summary=extracted_summary,
        exam_category=exam_category,
        subject=subject,
        material_type=material_type,
        year=year,
    )
    if not item:
        stmt = select(StagingQueue).where(
            or_(StagingQueue.source_url == source_url, StagingQueue.pdf_url == pdf_url)
        )
        res = await session.execute(stmt)
        item = res.scalar_one_or_none()
    return item


async def update_staging_status(
    session: AsyncSession,
    staging_id: Optional[int] = None,
    item_id: Optional[int] = None,
    status: StagingStatus = StagingStatus.PENDING,
    staging_message_id: Optional[int] = None,
) -> Optional[StagingQueue]:
    """Update moderation status and message ID for a staging queue draft."""
    sid = staging_id if staging_id is not None else item_id
    if sid is None:
        return None
    stg_item = await get_staging_item_by_id(session, staging_id=sid)
    if stg_item:
        stg_item.status = status
        if staging_message_id is not None:
            stg_item.staging_message_id = staging_message_id
        session.add(stg_item)
        await session.commit()
        await session.refresh(stg_item)
    return stg_item


async def get_staging_item_by_id(
    session: AsyncSession,
    staging_id: Optional[int] = None,
    item_id: Optional[int] = None,
) -> Optional[StagingQueue]:
    """Fetch staging item by ID supporting either staging_id or item_id parameter."""
    sid = staging_id if staging_id is not None else item_id
    if sid is None:
        return None
    stmt = select(StagingQueue).where(StagingQueue.id == sid)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def approve_staging_item(
    session: AsyncSession,
    staging_id: int,
    telegram_file_id: Optional[str] = None,
) -> Optional[StudyMaterial]:
    """Approve a staging draft and promote it to verified study material."""
    stg_item = await get_staging_item_by_id(session, staging_id=staging_id)
    if not stg_item or stg_item.status != StagingStatus.PENDING:
        return None

    # Update staging status
    stg_item.status = StagingStatus.APPROVED
    session.add(stg_item)

    # Promote to public StudyMaterial
    material = StudyMaterial(
        title=stg_item.title,
        exam_category=stg_item.exam_category,
        subject=stg_item.subject,
        material_type=stg_item.material_type,
        year=stg_item.year,
        file_path=stg_item.pdf_url or stg_item.source_url,
        telegram_file_id=telegram_file_id,
    )
    session.add(material)
    await session.commit()
    await session.refresh(material)
    return material


async def discard_staging_item(
    session: AsyncSession,
    staging_id: int,
) -> bool:
    """Mark a staging draft item as rejected."""
    stg_item = await get_staging_item_by_id(session, staging_id=staging_id)
    if not stg_item or stg_item.status != StagingStatus.PENDING:
        return False

    stg_item.status = StagingStatus.REJECTED
    session.add(stg_item)
    await session.commit()
    return True
