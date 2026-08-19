"""SQLAlchemy 2.0 Database Models with High-Performance Indexing."""

from datetime import datetime, timezone
import enum
from typing import Optional
from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


class ExamCategory(str, enum.Enum):
    """Target competitive exam category classification."""
    MPSC = "MPSC"
    POLICE_BHARTI = "POLICE_BHARTI"
    BANKING = "BANKING"
    SARAL_SEVA = "SARAL_SEVA"
    GENERAL = "GENERAL"


class MaterialType(str, enum.Enum):
    """Classification of educational document types."""
    GR = "GR"                              # Government Resolution (शासन निर्णय)
    PYQ = "PYQ"                            # Previous Year Question Paper
    SHORT_NOTES = "SHORT_NOTES"            # High-yield Revision Notes
    SYLLABUS = "SYLLABUS"                  # Official Exam Syllabus & Pattern
    TEST_PAPER = "TEST_PAPER"              # Mock Tests / Practice Papers
    CURRENT_AFFAIRS = "CURRENT_AFFAIRS"    # Daily / Monthly Current Affairs Digest


class StagingStatus(str, enum.Enum):
    """Approval lifecycle states for scraped documents."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class StudyMaterial(Base):
    """Verified competitive exam study materials repository."""

    __tablename__ = "study_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    exam_category: Mapped[ExamCategory] = mapped_column(
        SAEnum(ExamCategory, native_enum=False),
        default=ExamCategory.GENERAL,
        nullable=False,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(100), default="General", nullable=False, index=True)
    material_type: Mapped[MaterialType] = mapped_column(
        SAEnum(MaterialType, native_enum=False),
        default=MaterialType.GR,
        nullable=False,
        index=True,
    )
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    telegram_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_materials_lookup", "exam_category", "subject", "material_type", "year"),
        Index("ix_materials_search_opt", "exam_category", "material_type", "created_at"),
        Index("ix_materials_file_id", "telegram_file_id"),
    )

    def __repr__(self) -> str:
        return f"<StudyMaterial(id={self.id}, title='{self.title[:30]}', category='{self.exam_category}', type='{self.material_type}')>"


class StagingQueue(Base):
    """Staging queue for scraper drafts awaiting admin approval before broadcast."""

    __tablename__ = "staging_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True, index=True)
    pdf_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    extracted_summary: Mapped[str] = mapped_column(Text, nullable=False)
    exam_category: Mapped[ExamCategory] = mapped_column(
        SAEnum(ExamCategory, native_enum=False),
        default=ExamCategory.GENERAL,
        nullable=False,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(100), default="General", nullable=False)
    material_type: Mapped[MaterialType] = mapped_column(
        SAEnum(MaterialType, native_enum=False),
        default=MaterialType.GR,
        nullable=False,
        index=True,
    )
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[StagingStatus] = mapped_column(
        SAEnum(StagingStatus, native_enum=False),
        default=StagingStatus.PENDING,
        nullable=False,
        index=True,
    )
    staging_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_staging_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<StagingQueue(id={self.id}, status='{self.status}', title='{self.title[:30]}')>"
