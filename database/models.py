"""SQLAlchemy 2.0 Database Models with Extended Ingestion Telemetry, Provenance & MTProto Source Registry."""

from datetime import datetime, timezone
import enum
from typing import Optional
from sqlalchemy import (
    Boolean,
    BigInteger,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
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
    """Target competitive & academic exam category classification."""
    # 1. Civil Services & State Exams
    UPSC = "UPSC"                          # UPSC Civil Services (IAS / IPS / IFS)
    MPSC = "MPSC"                          # MPSC (Rajyaseva & Combine Group B/C)
    POLICE_BHARTI = "POLICE_BHARTI"        # Maharashtra Police Bharti
    SARAL_SEVA = "SARAL_SEVA"              # Saral Seva (Talathi / ZP / Nagar Parishad)

    # 2. National Engineering & Medical
    JEE = "JEE"                            # JEE Main & Advanced (Engineering)
    NEET = "NEET"                          # NEET UG (Medical)

    # 3. School & Foundation
    BOARD_10_12 = "BOARD_10_12"            # 10th & 12th Board (SSC & HSC)
    NCERT = "NCERT"                        # NCERT Textbooks & Solutions (Class 6 - 12)

    # 4. Banking & Staff Selection
    BANKING = "BANKING"                    # IBPS / SBI / RBI
    SSC = "SSC"                            # SSC (CGL / CHSL / GD / MTS)

    # 5. General & Government Resolutions
    GENERAL = "GENERAL"                    # General Studies / GRs / All Exams


class MaterialType(str, enum.Enum):
    """Classification of educational document types."""
    GR = "GR"                              # Government Resolution (शासन निर्णय)
    PYQ = "PYQ"                            # Previous Year Question Paper
    SHORT_NOTES = "SHORT_NOTES"            # High-yield Revision Notes
    SYLLABUS = "SYLLABUS"                  # Official Exam Syllabus & Pattern
    TEST_PAPER = "TEST_PAPER"              # Mock Tests / Practice Papers
    CURRENT_AFFAIRS = "CURRENT_AFFAIRS"    # Daily / Monthly Current Affairs Digest


class SourceType(str, enum.Enum):
    """Strict Provenance Source Classification."""
    OFFICIAL = "OFFICIAL"                  # Direct government or exam board portal
    AUTHORIZED = "AUTHORIZED"              # Approved educational Telegram channels / university repositories
    ADMIN = "ADMIN"                        # Admin-verified physical document upload
    COMMUNITY = "COMMUNITY"                # Student / community submission (requires moderation)


class ChannelAuthStatus(str, enum.Enum):
    """Authorization status for external Telegram channels."""
    AUTHORIZED = "AUTHORIZED"              # Officially vetted & approved for automatic ingestion
    PUBLIC_OPEN = "PUBLIC_OPEN"            # Open public study channel (subject to strict usefulness filter)
    PENDING_REVIEW = "PENDING_REVIEW"      # Newly added channel awaiting admin verification
    REVOKED = "REVOKED"                    # Blocked / revoked source (strictly skipped)


class StagingStatus(str, enum.Enum):
    """Approval lifecycle states for scraped documents."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class StudyMaterial(Base):
    """Verified competitive exam study materials repository with strict provenance & hashes."""

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
    topic: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, default="General", index=True)
    language: Mapped[str] = mapped_column(String(50), nullable=False, default="Marathi", index=True)
    material_type: Mapped[MaterialType] = mapped_column(
        SAEnum(MaterialType, native_enum=False),
        default=MaterialType.GR,
        nullable=False,
        index=True,
    )
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    source_type: Mapped[SourceType] = mapped_column(
        SAEnum(SourceType, native_enum=False),
        default=SourceType.OFFICIAL,
        nullable=False,
        index=True,
    )
    source_name: Mapped[str] = mapped_column(String(200), nullable=False, default="Official Portal", index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True, index=True)
    source_doc_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=1)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quality_score: Mapped[int] = mapped_column(Integer, nullable=False, default=100, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="VERIFIED", index=True)
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
        Index("ix_materials_content_hash", "content_hash"),
        Index("ix_materials_source_provenance", "source_type", "source_url"),
    )

    def __repr__(self) -> str:
        return f"<StudyMaterial(id={self.id}, title='{self.title[:30]}', category='{self.exam_category}', type='{self.material_type}', source='{self.source_type}')>"


class TelegramChannelSource(Base):
    """Approved external Telegram channels registry for user-account collector."""

    __tablename__ = "telegram_channel_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    channel_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    exam_category: Mapped[ExamCategory] = mapped_column(
        SAEnum(ExamCategory, native_enum=False),
        default=ExamCategory.GENERAL,
        nullable=False,
        index=True,
    )
    authorization_status: Mapped[ChannelAuthStatus] = mapped_column(
        SAEnum(ChannelAuthStatus, native_enum=False),
        default=ChannelAuthStatus.AUTHORIZED,
        nullable=False,
        index=True,
    )
    last_scanned_msg_id: Mapped[int] = mapped_column(Integer, default=0)
    total_messages_scanned: Mapped[int] = mapped_column(Integer, default=0)
    total_pdfs_downloaded: Mapped[int] = mapped_column(Integer, default=0)
    total_verified: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<TelegramChannelSource(id={self.id}, username='@{self.channel_username}', title='{self.title}', status='{self.authorization_status}')>"


class StagingQueue(Base):
    """Staging queue for scraper drafts awaiting admin approval before broadcast."""

    __tablename__ = "staging_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True, index=True)
    pdf_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    extracted_summary: Mapped[Text] = mapped_column(Text, nullable=False)
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


class IngestionMetric(Base):
    """Audit metrics and ingestion telemetry for background harvesting workers."""

    __tablename__ = "ingestion_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(100), index=True)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="PORTAL", index=True)
    files_scanned: Mapped[int] = mapped_column(Integer, default=0)
    files_downloaded: Mapped[int] = mapped_column(Integer, default=0)
    files_processed: Mapped[int] = mapped_column(Integer, default=0)
    duplicates_detected: Mapped[int] = mapped_column(Integer, default=0)
    failures_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="SUCCESS", index=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<IngestionMetric(id={self.id}, source='{self.source_name}', processed={self.files_processed}, status='{self.status}')>"


class BackfillJobStatus(str, enum.Enum):
    """Lifecycle status of a detached mass backfill batch job."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class BackfillTaskStatus(str, enum.Enum):
    """Checkpoint and execution status of a single channel within a backfill job."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class BackfillJob(Base):
    """Persistent job state for mass Telegram harvesting operations."""

    __tablename__ = "backfill_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_uuid: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[BackfillJobStatus] = mapped_column(
        SAEnum(BackfillJobStatus, native_enum=False),
        default=BackfillJobStatus.PENDING,
        nullable=False,
        index=True,
    )
    total_channels: Mapped[int] = mapped_column(Integer, default=0)
    completed_channels: Mapped[int] = mapped_column(Integer, default=0)
    total_scanned: Mapped[int] = mapped_column(Integer, default=0)
    total_ingested: Mapped[int] = mapped_column(Integer, default=0)
    total_errors: Mapped[int] = mapped_column(Integer, default=0)
    worker_pid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    def __repr__(self) -> str:
        return f"<BackfillJob(id={self.id}, uuid='{self.job_uuid}', status='{self.status}', ingested={self.total_ingested})>"


class BackfillChannelTask(Base):
    """Per-channel task checkpoint and progress tracking for a backfill job."""

    __tablename__ = "backfill_channel_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("backfill_jobs.id", ondelete="CASCADE"), index=True, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    channel_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    exam_category: Mapped[ExamCategory] = mapped_column(
        SAEnum(ExamCategory, native_enum=False),
        default=ExamCategory.GENERAL,
        nullable=False,
    )
    status: Mapped[BackfillTaskStatus] = mapped_column(
        SAEnum(BackfillTaskStatus, native_enum=False),
        default=BackfillTaskStatus.PENDING,
        nullable=False,
        index=True,
    )
    last_successful_msg_id: Mapped[int] = mapped_column(Integer, default=0)
    messages_scanned: Mapped[int] = mapped_column(Integer, default=0)
    pdfs_ingested: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    def __repr__(self) -> str:
        return f"<BackfillChannelTask(id={self.id}, job_id={self.job_id}, channel='@{self.channel_username}', status='{self.status}', ingested={self.pdfs_ingested})>"

