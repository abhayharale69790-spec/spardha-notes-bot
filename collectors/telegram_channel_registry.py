"""Approved Telegram Channel Registry & Authorization Manager.

Maintains curated authorized public channels, authorization levels, and target exam categories.
"""

from dataclasses import dataclass
import logging
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from database import crud
from database.models import ChannelAuthStatus, ExamCategory, TelegramChannelSource

logger = logging.getLogger(__name__)


@dataclass
class ApprovedChannelConfig:
    channel_id: int
    channel_username: str
    title: str
    exam_category: ExamCategory
    authorization_status: ChannelAuthStatus = ChannelAuthStatus.AUTHORIZED
    description: str = ""


# Curated directory of approved educational Telegram channels for target categories
DEFAULT_APPROVED_CHANNELS: List[ApprovedChannelConfig] = [
    ApprovedChannelConfig(
        channel_id=-1004297360223,
        channel_username="spardhanoteshub",
        title="Spardha Notes Hub (Official Community)",
        exam_category=ExamCategory.GENERAL,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
        description="Official publication channel for Harale Digital Study Point",
    ),
    ApprovedChannelConfig(
        channel_id=-1001589412301,
        channel_username="mpsc_study_materials",
        title="MPSC Rajyaseva & Combine Study Hub",
        exam_category=ExamCategory.MPSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
        description="Vetted MPSC syllabus notes, PYQ papers, and Maharashtra state study compendiums",
    ),
    ApprovedChannelConfig(
        channel_id=-1001798324512,
        channel_username="maharashtra_police_bharti_hub",
        title="Maharashtra Police Bharti Study Point",
        exam_category=ExamCategory.POLICE_BHARTI,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
        description="Police Bharti Marathi grammar, maths, and legal study digests",
    ),
    ApprovedChannelConfig(
        channel_id=-1001645239801,
        channel_username="saral_seva_talathi_notes",
        title="Saral Seva & Talathi TCS Pattern Prep",
        exam_category=ExamCategory.SARAL_SEVA,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
        description="TCS/IBPS pattern question banks and English grammar master guides",
    ),
    ApprovedChannelConfig(
        channel_id=-1001923847510,
        channel_username="upsc_civil_services_library",
        title="UPSC CSE Prelims & Mains Resource Hub",
        exam_category=ExamCategory.UPSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
        description="UPSC standard reference material, solved PYQs, and CSAT notes",
    ),
    ApprovedChannelConfig(
        channel_id=-1001837462910,
        channel_username="ssc_cgl_chsl_preparation",
        title="SSC CGL & CHSL English & Maths Hub",
        exam_category=ExamCategory.SSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
        description="Advanced mathematics formulas, grammar rules, and 10-year question sets",
    ),
    ApprovedChannelConfig(
        channel_id=-1001748293019,
        channel_username="ibps_sbi_banking_digest",
        title="Banking Awareness & Speed Maths Point",
        exam_category=ExamCategory.BANKING,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
        description="Speed maths tricks, high-level reasoning puzzles, and RBI banking updates",
    ),
    ApprovedChannelConfig(
        channel_id=-1001892304918,
        channel_username="ncert_foundation_textbooks",
        title="NCERT Class 6 - 12 Complete Science & Maths",
        exam_category=ExamCategory.NCERT,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
        description="NCERT textbook PDFs and chapterwise conceptual summaries",
    ),
    ApprovedChannelConfig(
        channel_id=-1001938472918,
        channel_username="maharashtra_state_board_books",
        title="Maharashtra 10th SSC & 12th HSC Board Hub",
        exam_category=ExamCategory.BOARD_10_12,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
        description="eBalbharati state board textbooks and official question banks",
    ),
    ApprovedChannelConfig(
        channel_id=-1001648291049,
        channel_username="jee_neet_science_academy",
        title="NTA JEE & NEET UG High-Yield Notes",
        exam_category=ExamCategory.JEE,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
        description="Physics, Chemistry, and Biology chapterwise question banks and formulas",
    ),
]


class TelegramChannelRegistry:
    """Manages the lifecycle, permissions, and synchronization metadata of approved Telegram channels."""

    async def initialize_defaults(self, session: AsyncSession) -> List[TelegramChannelSource]:
        """Ensure all default approved channels exist in database."""
        sources: List[TelegramChannelSource] = []
        for cfg in DEFAULT_APPROVED_CHANNELS:
            ch = await crud.get_or_create_telegram_channel(
                session=session,
                channel_id=cfg.channel_id,
                channel_username=cfg.channel_username,
                title=cfg.title,
                exam_category=cfg.exam_category,
                authorization_status=cfg.authorization_status,
            )
            sources.append(ch)
        logger.info(f"Initialized {len(sources)} default approved Telegram channel sources.")
        return sources

    async def get_all_approved_sources(self, session: AsyncSession) -> List[TelegramChannelSource]:
        """Fetch all currently active authorized Telegram channels."""
        return list(await crud.get_all_active_telegram_channels(session))

    async def authorize_channel(
        self,
        session: AsyncSession,
        channel_id: int,
        channel_username: Optional[str],
        title: str,
        exam_category: ExamCategory,
    ) -> TelegramChannelSource:
        """Register or authorize a new educational channel."""
        ch = await crud.get_or_create_telegram_channel(
            session=session,
            channel_id=channel_id,
            channel_username=channel_username,
            title=title,
            exam_category=exam_category,
            authorization_status=ChannelAuthStatus.AUTHORIZED,
        )
        logger.info(f"Authorized Telegram channel '{title}' (@{channel_username}) for #{exam_category.value}.")
        return ch


telegram_channel_registry = TelegramChannelRegistry()
