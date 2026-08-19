"""Asynchronous Web Scrapers and Portal Monitors with Multi-Tier Examination Coverage."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import logging
import re
from typing import List, Optional, Set
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from config.settings import get_settings
from database import crud
from database.models import ExamCategory, MaterialType, StagingStatus
from database.session import get_session
from scraper.client import ResilientHttpClient

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ScrapedNotice:
    """Standardized data representation of a scraped exam notice or document."""
    title: str
    source_url: str
    pdf_url: str
    summary: str
    exam_category: ExamCategory
    subject: str
    material_type: MaterialType
    year: Optional[int] = None


def generate_3point_bilingual_summary(
    title: str,
    department: str,
    notice_type: str,
    details: Optional[str] = None,
    exam_tag: str = "Exam",
) -> str:
    """Generate concise 3-point bilingual summary (Marathi & English) for staging review."""
    clean_title = title.strip()
    now_date = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    point_1 = f"🏛️ <b>विभाग व स्वरूप (Dept & Type):</b> {department} — {notice_type}"
    if details:
        point_2 = f"📋 <b>महत्त्वाचा तपशील (Key Details):</b> {details[:240]}"
    else:
        point_2 = (
            "📋 <b>महत्त्वाचा तपशील (Key Details):</b> सदर परीक्षेबाबत अधिकृत घोषणा प्रसिद्ध करण्यात आली आहे. "
            "सविस्तर माहितीसाठी जोडलेली अधिकृत PDF फाईल तपासावी."
        )

    point_3 = f"🎯 <b>लक्ष्य परीक्षा व दिनांक (Target & Date):</b> {exam_tag} | दिनांक: {now_date}"
    return f"1️⃣ {point_1}\n2️⃣ {point_2}\n3️⃣ {point_3}"


class BasePortalWatcher:
    """Abstract base class for all portal scrapers."""

    name: str = "BaseWatcher"
    source_url: str = ""
    default_category: ExamCategory = ExamCategory.GENERAL
    default_material_type: MaterialType = MaterialType.GR

    def __init__(self, http_client: Optional[ResilientHttpClient] = None) -> None:
        self.client = http_client or ResilientHttpClient()

    async def fetch_html(self) -> str:
        """Fetch raw HTML content using resilient HTTP client."""
        return await self.client.get_text(self.source_url)

    def parse_notices(self, html: str) -> List[ScrapedNotice]:
        """Parse HTML string and extract list of standardized notices."""
        raise NotImplementedError("Subclasses must implement parse_notices()")


class MPSCWatcher(BasePortalWatcher):
    """Monitor MPSC announcements, syllabi, circulars, and PYQs."""

    name = "MPSC_Watcher"
    source_url = "https://mpsc.gov.in/announcements"
    default_category = ExamCategory.MPSC
    default_material_type = MaterialType.SYLLABUS

    def parse_notices(self, html: str) -> List[ScrapedNotice]:
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        notices: List[ScrapedNotice] = []
        seen_urls: Set[str] = set()

        rows = soup.find_all(["tr", "li", "div"], class_=re.compile(r"announcement|notice|update|item", re.I))
        if not rows:
            rows = soup.find_all("a", href=re.compile(r"\.pdf|announcements", re.I))

        for item in rows[:25]:
            try:
                a_tag = item if item.name == "a" else item.find("a")
                if not a_tag or not a_tag.get("href"):
                    continue

                title = a_tag.get_text(strip=True)
                if not title or len(title) < 5:
                    continue

                pdf_url = urljoin(self.source_url, a_tag["href"])
                if pdf_url in seen_urls:
                    continue
                seen_urls.add(pdf_url)

                year_match = re.search(r"\b(202[0-9])\b", title)
                year = int(year_match.group(1)) if year_match else datetime.now().year

                mat_type = MaterialType.PYQ if "question paper" in title.lower() or "pyq" in title.lower() else MaterialType.SYLLABUS

                summary = generate_3point_bilingual_summary(
                    title=title,
                    department="महाराष्ट्र लोकसेवा आयोग (MPSC)",
                    notice_type="नवीन प्रसिद्धीपत्रक / अभ्यासक्रम",
                    details=f"MPSC अधिकृत घोषणा: {title[:200]}",
                    exam_tag="MPSC राज्यसेवा / संयुक्त गट ब व क",
                )

                notices.append(
                    ScrapedNotice(
                        title=title[:400],
                        source_url=self.source_url,
                        pdf_url=pdf_url,
                        summary=summary,
                        exam_category=ExamCategory.MPSC,
                        subject="अधिकृत परिपत्रक / जाहिरात",
                        material_type=mat_type,
                        year=year,
                    )
                )
            except Exception as e:
                logger.warning(f"[{self.name}] Error parsing item: {e}")
                continue

        return notices


class PoliceBhartiWatcher(BasePortalWatcher):
    """Monitor Police Recruitment circulars, physical criteria, and lists."""

    name = "PoliceBharti_Watcher"
    source_url = "https://mahapolice.gov.in/recruitment"
    default_category = ExamCategory.POLICE_BHARTI
    default_material_type = MaterialType.SYLLABUS

    def parse_notices(self, html: str) -> List[ScrapedNotice]:
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        notices: List[ScrapedNotice] = []
        seen_urls: Set[str] = set()

        links = soup.find_all("a", href=re.compile(r"\.pdf|recruitment|download", re.I))
        for a_tag in links[:15]:
            try:
                title = a_tag.get_text(strip=True)
                if not title or len(title) < 5:
                    continue

                pdf_url = urljoin(self.source_url, a_tag["href"])
                if pdf_url in seen_urls:
                    continue
                seen_urls.add(pdf_url)

                year_match = re.search(r"\b(202[0-9])\b", title)
                year = int(year_match.group(1)) if year_match else datetime.now().year

                summary = generate_3point_bilingual_summary(
                    title=title,
                    department="महाराष्ट्र पोलीस भरती मंडळ (MahaPolice)",
                    notice_type="पोलीस भरती सूचना / निकाल",
                    details=f"महाराष्ट्र पोलीस भरती परिपत्रक: {title}",
                    exam_tag="पोलीस भरती (Police Bharti)",
                )

                notices.append(
                    ScrapedNotice(
                        title=title[:400],
                        source_url=self.source_url,
                        pdf_url=pdf_url,
                        summary=summary,
                        exam_category=ExamCategory.POLICE_BHARTI,
                        subject="पोलीस भरती प्रक्रिया",
                        material_type=MaterialType.SYLLABUS,
                        year=year,
                    )
                )
            except Exception as e:
                logger.warning(f"[{self.name}] Error parsing link: {e}")
                continue

        return notices


class SaralSevaWatcher(BasePortalWatcher):
    """Monitor Saral Seva, Talathi, Zilla Parishad, and Nagar Parishad portals."""

    name = "SaralSeva_Watcher"
    source_url = "https://mahabhumi.gov.in/mahabhumilink"
    default_category = ExamCategory.SARAL_SEVA
    default_material_type = MaterialType.SYLLABUS

    def parse_notices(self, html: str) -> List[ScrapedNotice]:
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        notices: List[ScrapedNotice] = []
        seen_urls: Set[str] = set()

        links = soup.find_all("a", href=re.compile(r"\.pdf|notification|bharti", re.I))
        for a_tag in links[:15]:
            try:
                title = a_tag.get_text(strip=True)
                if not title or len(title) < 5:
                    continue

                pdf_url = urljoin(self.source_url, a_tag["href"])
                if pdf_url in seen_urls:
                    continue
                seen_urls.add(pdf_url)

                year_match = re.search(r"\b(202[0-9])\b", title)
                year = int(year_match.group(1)) if year_match else datetime.now().year

                summary = generate_3point_bilingual_summary(
                    title=title,
                    department="महसूल विभाग / सरळ सेवा (Saral Seva / Talathi)",
                    notice_type="सरळ सेवा जाहिरात / परिपत्रक",
                    details=f"तलाठी / जिल्हा परिषद / सरळ सेवा भरती माहिती: {title}",
                    exam_tag="सरळ सेवा (Saral Seva / ZP / Talathi)",
                )

                notices.append(
                    ScrapedNotice(
                        title=title[:400],
                        source_url=self.source_url,
                        pdf_url=pdf_url,
                        summary=summary,
                        exam_category=ExamCategory.SARAL_SEVA,
                        subject="सामान्य ज्ञान / सरळ सेवा",
                        material_type=MaterialType.SYLLABUS,
                        year=year,
                    )
                )
            except Exception as e:
                logger.warning(f"[{self.name}] Error parsing link: {e}")
                continue

        return notices


class UPSCWatcher(BasePortalWatcher):
    """Monitor UPSC examination notices, schedules, and question papers."""

    name = "UPSC_Watcher"
    source_url = "https://upsc.gov.in/examinations/active-examinations"
    default_category = ExamCategory.UPSC
    default_material_type = MaterialType.SYLLABUS

    def parse_notices(self, html: str) -> List[ScrapedNotice]:
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        notices: List[ScrapedNotice] = []
        seen_urls: Set[str] = set()

        links = soup.find_all("a", href=re.compile(r"\.pdf|examination|notification", re.I))
        for a_tag in links[:20]:
            try:
                title = a_tag.get_text(strip=True)
                if not title or len(title) < 6:
                    continue

                pdf_url = urljoin(self.source_url, a_tag["href"])
                if pdf_url in seen_urls:
                    continue
                seen_urls.add(pdf_url)

                year_match = re.search(r"\b(202[0-9])\b", title)
                year = int(year_match.group(1)) if year_match else datetime.now().year

                summary = generate_3point_bilingual_summary(
                    title=title,
                    department="Union Public Service Commission (UPSC)",
                    notice_type="Civil Services Examination Notice",
                    details=f"UPSC Official Notification: {title[:200]}",
                    exam_tag="UPSC Civil Services / NDA / CDS",
                )

                notices.append(
                    ScrapedNotice(
                        title=title[:400],
                        source_url=self.source_url,
                        pdf_url=pdf_url,
                        summary=summary,
                        exam_category=ExamCategory.UPSC,
                        subject="UPSC Notification",
                        material_type=MaterialType.SYLLABUS,
                        year=year,
                    )
                )
            except Exception as e:
                logger.warning(f"[{self.name}] Error parsing UPSC link: {e}")
                continue

        return notices


class NTAWatcher(BasePortalWatcher):
    """Monitor National Testing Agency (NTA) for JEE Main & NEET UG updates."""

    name = "NTA_Watcher"
    source_url = "https://nta.ac.in/NoticeBoard"
    default_category = ExamCategory.JEE
    default_material_type = MaterialType.SYLLABUS

    def parse_notices(self, html: str) -> List[ScrapedNotice]:
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        notices: List[ScrapedNotice] = []
        seen_urls: Set[str] = set()

        links = soup.find_all("a", href=re.compile(r"\.pdf|download|notice", re.I))
        for a_tag in links[:20]:
            try:
                title = a_tag.get_text(strip=True)
                if not title or len(title) < 6:
                    continue

                pdf_url = urljoin(self.source_url, a_tag["href"])
                if pdf_url in seen_urls:
                    continue
                seen_urls.add(pdf_url)

                is_neet = bool(re.search(r"neet", title, re.I))
                category = ExamCategory.NEET if is_neet else ExamCategory.JEE

                year_match = re.search(r"\b(202[0-9])\b", title)
                year = int(year_match.group(1)) if year_match else datetime.now().year

                summary = generate_3point_bilingual_summary(
                    title=title,
                    department="National Testing Agency (NTA)",
                    notice_type="Public Notice / Answer Key",
                    details=f"NTA National Exam Announcement: {title[:200]}",
                    exam_tag="NEET UG / JEE Main" if is_neet else "JEE Main & Advanced",
                )

                notices.append(
                    ScrapedNotice(
                        title=title[:400],
                        source_url=self.source_url,
                        pdf_url=pdf_url,
                        summary=summary,
                        exam_category=category,
                        subject="NTA Official Circular",
                        material_type=MaterialType.SYLLABUS,
                        year=year,
                    )
                )
            except Exception as e:
                logger.warning(f"[{self.name}] Error parsing NTA link: {e}")
                continue

        return notices


class MahaGRWatcher(BasePortalWatcher):
    """Monitor Maharashtra Government Resolutions (GR) on maharashtra.gov.in."""

    name = "MahaGR_Watcher"
    source_url = "https://www.maharashtra.gov.in/1145/Government-Resolutions"
    default_category = ExamCategory.GENERAL
    default_material_type = MaterialType.GR

    def parse_notices(self, html: str) -> List[ScrapedNotice]:
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        notices: List[ScrapedNotice] = []
        seen_urls: Set[str] = set()

        links = soup.find_all("a", href=re.compile(r"\.pdf|GR|download", re.I))
        for a_tag in links[:20]:
            try:
                title = a_tag.get_text(strip=True)
                if not title or len(title) < 8:
                    continue

                pdf_url = urljoin(self.source_url, a_tag["href"])
                if pdf_url in seen_urls:
                    continue
                seen_urls.add(pdf_url)

                year_match = re.search(r"\b(202[0-9])\b", title)
                year = int(year_match.group(1)) if year_match else datetime.now().year

                summary = generate_3point_bilingual_summary(
                    title=title,
                    department="महाराष्ट्र शासन (Govt of Maharashtra)",
                    notice_type="शासन निर्णय (Government Resolution)",
                    details=f"महाराष्ट्र शासनाचा अधिकृत निर्णय: {title[:200]}",
                    exam_tag="सामान्य प्रशासन व सर्व स्पर्धा परीक्षा",
                )

                notices.append(
                    ScrapedNotice(
                        title=title[:400],
                        source_url=self.source_url,
                        pdf_url=pdf_url,
                        summary=summary,
                        exam_category=ExamCategory.GENERAL,
                        subject="शासन निर्णय (GR)",
                        material_type=MaterialType.GR,
                        year=year,
                    )
                )
            except Exception as e:
                logger.warning(f"[{self.name}] Error parsing GR link: {e}")
                continue

        return notices


class ScraperOrchestrator:
    """Coordinates periodic execution of all multi-portal watchers and routes new items to staging."""

    def __init__(self, http_client: Optional[ResilientHttpClient] = None) -> None:
        self.http_client = http_client or ResilientHttpClient()
        self.watchers: List[BasePortalWatcher] = [
            MPSCWatcher(http_client=self.http_client),
            UPSCWatcher(http_client=self.http_client),
            NTAWatcher(http_client=self.http_client),
            PoliceBhartiWatcher(http_client=self.http_client),
            SaralSevaWatcher(http_client=self.http_client),
            MahaGRWatcher(http_client=self.http_client),
        ]

    async def run_scrape_cycle(self, staging_sender: Optional[object] = None) -> int:
        """Execute one complete scraping round across all portals. Returns count of new items queued."""
        logger.info("Starting scheduled multi-portal scraping cycle...")
        new_items_count = 0

        for watcher in self.watchers:
            try:
                logger.info(f"Checking portal: {watcher.name} ({watcher.source_url})")
                html = await watcher.fetch_html()
                if not html:
                    continue

                notices = watcher.parse_notices(html)
                logger.info(f"[{watcher.name}] Found {len(notices)} potential notice candidates")

                async with get_session() as session:
                    for notice in notices:
                        is_known = await crud.is_url_already_known(
                            session=session,
                            source_url=notice.source_url,
                            pdf_url=notice.pdf_url,
                        )
                        if is_known:
                            continue

                        staging_item = await crud.create_staging_item(
                            session=session,
                            title=notice.title,
                            source_url=notice.source_url,
                            pdf_url=notice.pdf_url,
                            extracted_summary=notice.summary,
                            exam_category=notice.exam_category,
                            subject=notice.subject,
                            material_type=notice.material_type,
                            year=notice.year,
                        )
                        if not staging_item:
                            continue

                        new_items_count += 1
                        logger.info(f"Queued new item for admin approval: [ID: {staging_item.id}] {staging_item.title[:40]}")

                        if staging_sender and hasattr(staging_sender, "post_draft_to_staging"):
                            try:
                                msg_id = await staging_sender.post_draft_to_staging(staging_item)
                                if msg_id:
                                    staging_item.staging_message_id = msg_id
                                    await session.commit()
                            except Exception as post_err:
                                logger.error(f"Failed to post staging item {staging_item.id}: {post_err}")

            except Exception as w_err:
                logger.error(f"Error during {watcher.name} execution: {w_err}")

        logger.info(f"Multi-portal scraping cycle completed. Queued {new_items_count} new items.")
        return new_items_count
