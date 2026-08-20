"""Central Source Registry for Multi-Source Study Material Harvesting."""

from dataclasses import dataclass, field
import enum
from typing import Dict, List, Optional
from database.models import ExamCategory, MaterialType


class SourceType(str, enum.Enum):
    """Supported source ingestion protocol types."""
    PORTAL = "PORTAL"          # Official government & exam portals (HTML scraping)
    GDRIVE = "GDRIVE"          # Google Drive / Cloud shared folders
    TELEGRAM = "TELEGRAM"      # Telegram channels & community forwards
    RSS = "RSS"                # RSS feeds & atomic updates
    API = "API"                # REST APIs & JSON repositories
    WEB = "WEB"                # Public educational digital libraries


@dataclass
class RegisteredSource:
    """Configuration and metadata definition for an educational material source."""
    source_id: str
    name: str
    source_type: SourceType
    url: str
    exam_category: ExamCategory
    default_subject: str
    default_material_type: MaterialType
    language: str = "Marathi"
    enabled: bool = True
    scrape_interval_minutes: int = 60
    headers: Dict[str, str] = field(default_factory=dict)
    extra_params: Dict[str, str] = field(default_factory=dict)


# Default catalog of authorized, verified official educational repositories
DEFAULT_REGISTERED_SOURCES: List[RegisteredSource] = [
    # 1. School & State Board (eBalbharati)
    RegisteredSource(
        source_id="ebalbharati_10th_ssc",
        name="eBalbharati 10th SSC Board Repository",
        source_type=SourceType.PORTAL,
        url="https://ebalbharati.in/",
        exam_category=ExamCategory.BOARD_10_12,
        default_subject="10th SSC Board",
        default_material_type=MaterialType.TEST_PAPER,
        language="Marathi",
    ),
    RegisteredSource(
        source_id="ebalbharati_12th_hsc",
        name="eBalbharati 12th HSC Science & Arts Repository",
        source_type=SourceType.PORTAL,
        url="https://ebalbharati.in/",
        exam_category=ExamCategory.BOARD_10_12,
        default_subject="12th HSC Board",
        default_material_type=MaterialType.TEST_PAPER,
        language="Bilingual",
    ),
    RegisteredSource(
        source_id="ncert_foundation_portal",
        name="NCERT Official Textbook Repository (Class 6-12)",
        source_type=SourceType.PORTAL,
        url="https://ncert.nic.in/textbook.php",
        exam_category=ExamCategory.NCERT,
        default_subject="NCERT Science & Maths",
        default_material_type=MaterialType.SHORT_NOTES,
        language="Bilingual",
    ),

    # 2. National Engineering & Medical (JEE & NEET)
    RegisteredSource(
        source_id="nta_jee_main_portal",
        name="NTA Official JEE Main & Advanced Portal",
        source_type=SourceType.PORTAL,
        url="https://nta.ac.in/Downloads",
        exam_category=ExamCategory.JEE,
        default_subject="Physics / Chemistry / Maths",
        default_material_type=MaterialType.PYQ,
        language="English",
    ),
    RegisteredSource(
        source_id="nta_neet_ug_portal",
        name="NTA Official NEET UG Medical Portal",
        source_type=SourceType.PORTAL,
        url="https://nta.ac.in/Downloads",
        exam_category=ExamCategory.NEET,
        default_subject="Biology & Physiology",
        default_material_type=MaterialType.PYQ,
        language="English",
    ),

    # 3. Civil Services & State Exams (MPSC & UPSC)
    RegisteredSource(
        source_id="mpsc_announcements_portal",
        name="MPSC Maharashtra Public Service Commission",
        source_type=SourceType.PORTAL,
        url="https://mpsc.gov.in/announcements",
        exam_category=ExamCategory.MPSC,
        default_subject="राज्यशास्त्र व इतिहास",
        default_material_type=MaterialType.SYLLABUS,
        language="Marathi",
    ),
    RegisteredSource(
        source_id="upsc_prelims_portal",
        name="UPSC Union Public Service Commission",
        source_type=SourceType.PORTAL,
        url="https://upsc.gov.in/examinations/previous-question-papers",
        exam_category=ExamCategory.UPSC,
        default_subject="General Studies & CSAT",
        default_material_type=MaterialType.PYQ,
        language="Bilingual",
    ),

    # 4. State Recruitment & Police
    RegisteredSource(
        source_id="mahapolice_recruitment_portal",
        name="Maharashtra State Police Recruitment Board",
        source_type=SourceType.PORTAL,
        url="https://mahapolice.gov.in/recruitment",
        exam_category=ExamCategory.POLICE_BHARTI,
        default_subject="पोलीस भरती सराव प्रश्नसंच",
        default_material_type=MaterialType.TEST_PAPER,
        language="Marathi",
    ),
    RegisteredSource(
        source_id="mahabhumi_saralseva_portal",
        name="Mahabhumi & Saral Seva Talathi/ZP Board",
        source_type=SourceType.PORTAL,
        url="https://mahabhumi.gov.in/mahabhumilink",
        exam_category=ExamCategory.SARAL_SEVA,
        default_subject="तलाठी व जिल्हा परिषद भरती",
        default_material_type=MaterialType.TEST_PAPER,
        language="Marathi",
    ),

    # 5. Banking & Staff Selection
    RegisteredSource(
        source_id="ibps_banking_portal",
        name="IBPS & Banking Examination Center",
        source_type=SourceType.PORTAL,
        url="https://www.ibps.in/",
        exam_category=ExamCategory.BANKING,
        default_subject="Quantitative Aptitude & Reasoning",
        default_material_type=MaterialType.TEST_PAPER,
        language="English",
    ),
    RegisteredSource(
        source_id="ssc_cgl_portal",
        name="Staff Selection Commission (SSC CGL/CHSL)",
        source_type=SourceType.PORTAL,
        url="https://ssc.gov.in/",
        exam_category=ExamCategory.SSC,
        default_subject="Quantitative Maths & English",
        default_material_type=MaterialType.PYQ,
        language="Bilingual",
    ),


    # 6. Maharashtra Government Resolutions
    RegisteredSource(
        source_id="maharashtra_gr_portal",
        name="Maharashtra Government Resolutions (GR) Portal",
        source_type=SourceType.PORTAL,
        url="https://www.maharashtra.gov.in/1145/Government-Resolutions",
        exam_category=ExamCategory.GENERAL,
        default_subject="शासन निर्णय (GR)",
        default_material_type=MaterialType.GR,
        language="Marathi",
    ),

    # 7. Cloud Storage & Google Drive Feeds
    RegisteredSource(
        source_id="gdrive_study_hub",
        name="Google Drive Study Hub & Open Drive Folders",
        source_type=SourceType.GDRIVE,
        url="https://drive.google.com/drive/folders/spardha_study_hub",
        exam_category=ExamCategory.GENERAL,
        default_subject="डिजिटल स्टडी ड्राईव्ह",
        default_material_type=MaterialType.SHORT_NOTES,
        language="Marathi",
    ),

    # 8. Community & Telegram Ingestion
    RegisteredSource(
        source_id="telegram_spardha_hub",
        name="Telegram Spardha Notes Hub (@spardhanoteshub)",
        source_type=SourceType.TELEGRAM,
        url="https://t.me/spardhanoteshub",
        exam_category=ExamCategory.GENERAL,
        default_subject="हस्तलिखित नोट्स",
        default_material_type=MaterialType.SHORT_NOTES,
        language="Marathi",
    ),
]


class SourceRegistry:
    """Thread-safe source registry providing dynamic discovery and management."""

    def __init__(self, sources: Optional[List[RegisteredSource]] = None) -> None:
        self._sources: Dict[str, RegisteredSource] = {
            s.source_id: s for s in (sources or DEFAULT_REGISTERED_SOURCES)
        }

    def get_all_sources(self, enabled_only: bool = True) -> List[RegisteredSource]:
        """Return list of all registered educational sources."""
        if enabled_only:
            return [s for s in self._sources.values() if s.enabled]
        return list(self._sources.values())

    def get_source_by_id(self, source_id: str) -> Optional[RegisteredSource]:
        """Fetch registered source by unique ID."""
        return self._sources.get(source_id)

    def get_sources_by_category(self, category: ExamCategory) -> List[RegisteredSource]:
        """Filter registered sources by target exam category."""
        return [s for s in self._sources.values() if s.exam_category == category and s.enabled]

    def get_sources_for_category(self, category: ExamCategory) -> List[RegisteredSource]:
        """Alias for get_sources_by_category."""
        return self.get_sources_by_category(category)


    def register_source(self, source: RegisteredSource) -> None:
        """Register a new custom source dynamically."""
        self._sources[source.source_id] = source

    def disable_source(self, source_id: str) -> bool:
        """Disable a registered source by ID."""
        if source_id in self._sources:
            self._sources[source_id].enabled = False
            return True
        return False


# Global singleton source registry
source_registry = SourceRegistry()
