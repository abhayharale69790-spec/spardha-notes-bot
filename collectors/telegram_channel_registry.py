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
    redistribution_authorized: bool = True
    monitoring_mode: str = "CONTINUOUS"  # "CONTINUOUS" or "HISTORICAL_ONLY"
    description: str = ""


# Curated directory of approved educational Telegram channels for target categories
DEFAULT_APPROVED_CHANNELS: List[ApprovedChannelConfig] = [
    # Hub Channel
    ApprovedChannelConfig(
        channel_id=-1004297360223,
        channel_username="spardhanoteshub",
        title="Spardha Notes Hub (Official Community)",
        exam_category=ExamCategory.GENERAL,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
        redistribution_authorized=True,
        monitoring_mode="CONTINUOUS",
        description="Official publication channel for Harale Digital Study Point",
    ),

    # 1. MPSC
    ApprovedChannelConfig(
        channel_id=-1001589412301,
        channel_username="mpsc_StudyCampus",
        title="📎MPSC Study Campus",
        exam_category=ExamCategory.MPSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
        redistribution_authorized=True,
        monitoring_mode="HISTORICAL_ONLY",  # Frozen after msg #1803 (March 2021)
        description="Historical MPSC Study Notes Archive",
    ),

    ApprovedChannelConfig(
        channel_id=-1001589412302,
        channel_username="MPSCHistory",
        title="MPSC History",
        exam_category=ExamCategory.MPSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-1001589412303,
        channel_username="MPSCmaths",
        title="MPSCmaths",
        exam_category=ExamCategory.MPSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-1001589412304,
        channel_username="MaharashtraSpardhaPariksha",
        title="महाराष्ट्र स्पर्धा परीक्षा (Official)",
        exam_category=ExamCategory.MPSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-1001589412305,
        channel_username="mpscguidnce",
        title="MPSC Guidance™",
        exam_category=ExamCategory.MPSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-1001589412306,
        channel_username="mpscsimplified",
        title="MPSC SIMPLIFIED(official)",
        exam_category=ExamCategory.MPSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-1001589412307,
        channel_username="mpsc_university",
        title="🎓𝙈𝙋𝙎𝘾 𝙐𝙉𝙄𝙑𝙀𝙍𝙎𝙄𝙏𝙔🚨",
        exam_category=ExamCategory.MPSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-1001589412308,
        channel_username="VidyaPrabodhiniMPSC",
        title="🇮🇳 Vidya Prabodhini MPSC",
        exam_category=ExamCategory.MPSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-1001589412309,
        channel_username="MpscMadeSimple",
        title="𝗠𝗽𝘀𝗰 𝗘𝘅𝗮𝗺 𝗠𝗮𝗻𝘁𝗿𝗮™",
        exam_category=ExamCategory.MPSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),

    # 2. Police Bharti
    ApprovedChannelConfig(
        channel_id=-1001798324513,
        channel_username="missionpolice2021",
        title="Mission Police bharti ™",
        exam_category=ExamCategory.POLICE_BHARTI,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-1001798324514,
        channel_username="Police_bharti_and_MPSC",
        title="POLICE BHARTI 2026 🚔👮‍♀️",
        exam_category=ExamCategory.POLICE_BHARTI,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-1001798324515,
        channel_username="MaharashtraPoliceBharati",
        title="महाराष्ट्र पोलीस भरती (Official)™",
        exam_category=ExamCategory.POLICE_BHARTI,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-1001798324516,
        channel_username="tikkarmarathi",
        title="TikKar Marathi - पोलीस भरती",
        exam_category=ExamCategory.POLICE_BHARTI,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-1001798324517,
        channel_username="vishalsirgk",
        title="GK by Vishal Sir",
        exam_category=ExamCategory.POLICE_BHARTI,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),

    # 3. Saral Seva / Talathi
    ApprovedChannelConfig(
        channel_id=-1001645239802,
        channel_username="mega_talathi_bharti",
        title="Talathi Bharti",
        exam_category=ExamCategory.SARAL_SEVA,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-1001645239803,
        channel_username="SuperCoachingMarathiby_Testbook",
        title="SuperCoaching Marathi by Testbook",
        exam_category=ExamCategory.SARAL_SEVA,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),

    # 4. SSC
    ApprovedChannelConfig(
        channel_id=-1001837462911,
        channel_username="ssccglpinnacleonline",
        title="Pinnacle Publications official",
        exam_category=ExamCategory.SSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-1001837462912,
        channel_username="Exam_Posts",
        title="ExamPost ™",
        exam_category=ExamCategory.SSC,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),

    # 5. Banking
    ApprovedChannelConfig(
        channel_id=-1001748293020,
        channel_username="banking_free_study_materials_pdf",
        title="Banking Free Study Material For SBI",
        exam_category=ExamCategory.BANKING,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),

    # 6. JEE & NEET
    ApprovedChannelConfig(
        channel_id=-1001648291050,
        channel_username="JEE_Full_Study_Material",
        title="JEE Full Study Material",
        exam_category=ExamCategory.JEE,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-1001648291051,
        channel_username="NEET_Full_Study_Material",
        title="NEET Full Study Material",
        exam_category=ExamCategory.NEET,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-1001892304919,
        channel_username="pdfstudymaterialss",
        title="JEE NEET PDF STUDY MATERIALS",
        exam_category=ExamCategory.NCERT,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),

    # 7. State Board 10th - 12th
    ApprovedChannelConfig(
        channel_id=-1001938472919,
        channel_username="mhsb_11_12",
        title="Maharashtra State Board Class 11 & 12",
        exam_category=ExamCategory.BOARD_10_12,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
    ),
    ApprovedChannelConfig(
        channel_id=-1001938472920,
        channel_username="maharashtra_state_boardbooks",
        title="Maharashtra State Board Books",
        exam_category=ExamCategory.BOARD_10_12,
        authorization_status=ChannelAuthStatus.AUTHORIZED,
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
                redistribution_authorized=cfg.redistribution_authorized,
                monitoring_mode=cfg.monitoring_mode,
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
        redistribution_authorized: bool = True,
        monitoring_mode: str = "CONTINUOUS",
    ) -> TelegramChannelSource:
        """Register or authorize a new educational channel."""
        ch = await crud.get_or_create_telegram_channel(
            session=session,
            channel_id=channel_id,
            channel_username=channel_username,
            title=title,
            exam_category=exam_category,
            authorization_status=ChannelAuthStatus.AUTHORIZED,
            redistribution_authorized=redistribution_authorized,
            monitoring_mode=monitoring_mode,
        )
        logger.info(f"Authorized Telegram channel '{title}' (@{channel_username}) for #{exam_category.value} (mode={monitoring_mode}).")
        return ch



telegram_channel_registry = TelegramChannelRegistry()
