"""Processing Worker: Asynchronous PDF Streaming Downloader, Hashing & Text Extractor."""

from dataclasses import dataclass
import hashlib
import io
import logging
import os
from pathlib import Path
import re
from typing import Optional, Tuple
import httpx
from pypdf import PdfReader
from scraper.client import ResilientHttpClient

logger = logging.getLogger(__name__)


@dataclass
class ProcessedDocument:
    """Standardized representation of an extracted, hashed, and classified study document."""
    file_path: str
    content_hash: str
    page_count: int
    extracted_text: str
    language: str
    detected_topic: str
    detected_year: Optional[int]
    file_size_bytes: int
    is_valid: bool = True
    error_message: Optional[str] = None


class ProcessingWorker:
    """Handles safe async downloading, SHA-256 fingerprinting, and pypdf text extraction."""

    def __init__(self, http_client: Optional[ResilientHttpClient] = None, download_dir: str = "downloads") -> None:
        self.client = http_client or ResilientHttpClient()
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        """Generate SHA-256 binary hash hex digest."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def detect_language(text: str) -> str:
        """Classify primary language of text excerpt."""
        if not text or len(text.strip()) < 10:
            return "Marathi"

        # Check Devanagari Unicode range (\u0900 - \u097F)
        devanagari_chars = len(re.findall(r"[\u0900-\u097F]", text))
        latin_chars = len(re.findall(r"[a-zA-Z]", text))

        if devanagari_chars > 0 and latin_chars > 0 and (devanagari_chars / (latin_chars + devanagari_chars) > 0.3):
            # Check Marathi specific words
            if re.search(r"\b(आहे|झाले|शासन|निर्णय|परीक्षा|प्रश्न|उत्तर|महाराष्ट्र)\b", text):
                return "Marathi"
            return "Bilingual"
        elif devanagari_chars > latin_chars:
            return "Marathi"
        elif latin_chars > 0:
            return "English"
        return "Marathi"

    @staticmethod
    def detect_topic(title: str, text: str, default_subject: str = "General") -> str:
        """Identify specific topic / syllabus tag from title and text."""
        combined = f"{title} {text[:500]}".lower()

        topic_rules = [
            (r"राज्यघटना|संविधान|घटना|polity|constitution", "भारतीय संविधान व राज्यघटना"),
            (r"इतिहास|history|स्वातंत्र्य|शिवकालीन", "आधुनिक भारताचा इतिहास"),
            (r"भूगोल|geography|नद्या|पर्वत|महाराष्ट्र भूगोल", "महाराष्ट्र व भारताचा भूगोल"),
            (r"अर्थशास्त्र|economics|बजेट|gdp|अर्थव्यवस्था", "भारतीय अर्थव्यवस्था"),
            (r"विज्ञान|physics|chemistry|biology|science|प्राणीशास्त्र", "सामान्य विज्ञान"),
            (r"अंकगणित|गणित|maths|algebra|geometry|शेकडेवारी", "अंकगणित व बीजगणित"),
            (r"बुद्धिमत्ता|reasoning|तर्कक्षमता|कोडिंग", "बुद्धिमत्ता चाचणी"),
            (r"मराठी व्याकरण|व्याकरण|संधी|समास|प्रयोग", "मराठी व्याकरण व शब्दसंग्रह"),
            (r"इंग्रजी|english grammar|vocabulary|comprehension", "English Grammar & Vocab"),
            (r"चालू घडामोडी|current affairs|पुरस्कार|क्रीडा", "चालू घडामोडी"),
            (r"शासन निर्णय|gr|परिपत्रक|भत्ता|आरक्षण", "शासन निर्णय व परिपत्रके"),
        ]

        for pattern, topic_name in topic_rules:
            if re.search(pattern, combined):
                return topic_name

        return default_subject

    async def download_and_process(
        self,
        url: str,
        title: str,
        default_subject: str = "General",
        max_bytes: int = 50 * 1024 * 1024,  # 50 MB limit
    ) -> ProcessedDocument:
        """Download URL safely, compute SHA256 hash, and extract document metadata."""
        if not (url.startswith("http://") or url.startswith("https://")):
            # Local file path or mock
            if os.path.exists(url):
                with open(url, "rb") as f:
                    content = f.read()
                return self.process_pdf_bytes(content, file_path=url, title=title, default_subject=default_subject)
            return ProcessedDocument(
                file_path=url,
                content_hash="",
                page_count=0,
                extracted_text="",
                language="Marathi",
                detected_topic=default_subject,
                detected_year=datetime.now().year if "datetime" in globals() else 2024,
                file_size_bytes=0,
                is_valid=False,
                error_message="Invalid file path or URL",
            )

        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return ProcessedDocument(
                        file_path=url,
                        content_hash="",
                        page_count=0,
                        extracted_text="",
                        language="Marathi",
                        detected_topic=default_subject,
                        detected_year=2024,
                        file_size_bytes=0,
                        is_valid=False,
                        error_message=f"HTTP status {resp.status_code}",
                    )

                content = resp.content
                if len(content) > max_bytes:
                    return ProcessedDocument(
                        file_path=url,
                        content_hash="",
                        page_count=0,
                        extracted_text="",
                        language="Marathi",
                        detected_topic=default_subject,
                        detected_year=2024,
                        file_size_bytes=len(content),
                        is_valid=False,
                        error_message=f"File exceeds max size limit of {max_bytes} bytes",
                    )

                return self.process_pdf_bytes(content, file_path=url, title=title, default_subject=default_subject)

        except Exception as err:
            logger.error(f"Download/process error for {url}: {err}")
            return ProcessedDocument(
                file_path=url,
                content_hash="",
                page_count=0,
                extracted_text="",
                language="Marathi",
                detected_topic=default_subject,
                detected_year=2024,
                file_size_bytes=0,
                is_valid=False,
                error_message=str(err),
            )

    def process_pdf_bytes(
        self,
        content: bytes,
        file_path: str,
        title: str,
        default_subject: str = "General",
    ) -> ProcessedDocument:
        """Parse in-memory PDF binary stream and extract text & structure."""
        content_hash = self.compute_sha256(content)
        file_size = len(content)

        # Magic Bytes Check (%PDF-)
        if not content.startswith(b"%PDF-"):
            return ProcessedDocument(
                file_path=file_path,
                content_hash=content_hash,
                page_count=0,
                extracted_text="",
                language="Marathi",
                detected_topic=default_subject,
                detected_year=2024,
                file_size_bytes=file_size,
                is_valid=False,
                error_message="Invalid magic bytes: File is not a valid PDF document",
            )

        try:
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                return ProcessedDocument(
                    file_path=file_path,
                    content_hash=content_hash,
                    page_count=0,
                    extracted_text="",
                    language="Marathi",
                    detected_topic=default_subject,
                    detected_year=2024,
                    file_size_bytes=file_size,
                    is_valid=False,
                    error_message="Document is password protected / encrypted",
                )

            page_count = len(reader.pages)
            extracted_text_parts = []

            # Extract up to first 5 pages for search index and summarization
            for p in reader.pages[:5]:
                try:
                    txt = p.extract_text()
                    if txt:
                        extracted_text_parts.append(txt)
                except Exception:
                    pass

            full_text = "\n".join(extracted_text_parts).strip()
            lang = self.detect_language(f"{title} {full_text}")
            topic = self.detect_topic(title=title, text=full_text, default_subject=default_subject)

            # Year extraction
            year_match = re.search(r"\b(201[5-9]|202[0-9])\b", f"{title} {full_text[:300]}")
            detected_year = int(year_match.group(1)) if year_match else 2024

            return ProcessedDocument(
                file_path=file_path,
                content_hash=content_hash,
                page_count=page_count,
                extracted_text=full_text[:1500],
                language=lang,
                detected_topic=topic,
                detected_year=detected_year,
                file_size_bytes=file_size,
                is_valid=True,
            )

        except Exception as parse_err:
            return ProcessedDocument(
                file_path=file_path,
                content_hash=content_hash,
                page_count=0,
                extracted_text="",
                language="Marathi",
                detected_topic=default_subject,
                detected_year=2024,
                file_size_bytes=file_size,
                is_valid=False,
                error_message=f"PDF parsing error: {parse_err}",
            )
