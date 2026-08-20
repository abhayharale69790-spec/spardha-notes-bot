"""Quality Worker: PDF Magic Header Validation, Strict Deduplication, Educational Usefulness & Scoring."""

import logging
import re
from typing import List, Optional, Set, Tuple
from rapidfuzz import fuzz, process
from workers.processing_worker import ProcessedDocument

logger = logging.getLogger(__name__)

# Patterns that indicate administrative or procurement noise (NOT educational study material)
ADMINISTRATIVE_NOISE_PATTERNS = [
    r"निविदा|ई-निविदा|निविदा सूचना|tender|rfp|rfq|quotation|procurement|bidder|empanelment",
    r"corrigendum|शुद्धिपत्रक|शुध्दीपत्रक|तारीख वाढ|date extension",
    r"अर्ज नमुना|application format|bio-?data form|registration form|blank form",
    r"बदली आदेश|स्थानांतरण|seniority list|ज्येष्ठता सूची|सेवानिवृत्ती|पदोन्नती आदेश",
    r"attendance sheet|हजेरी पत्रक|meeting agenda|बैठक कार्यवृत्त|minutes of meeting",
    r"दरपत्रक|कोटेशन|rate contract|work order|कार्यादेश",
]

# Patterns that confirm genuine educational value
EDUCATIONAL_CONTENT_PATTERNS = [
    r"अभ्यासक्रम|syllabus|परीक्षेचे स्वरूप|scheme of examination|exam pattern",
    r"प्रश्नपत्रिका|question paper|pyq|मागील प्रश्न|model paper|mock test|सराव प्रश्नसंच",
    r"नोट्स|notes|संकल्पना|formula|सूत्र|व्याकरण|grammar|पुस्तिका|handbook|guide",
    r"प्रकरण|chapter|धडा|unit|solution|उत्तरे|स्पष्टीकरण|answer key",
    r"घटना|कलम|इतिहास|भूगोल|विज्ञान|गणित|बुद्धिमत्ता|polity|history|geography|physics|chemistry|biology|maths",
    r"ncert|state board|balbharati|बालभारती|mpsc|upsc|jee|neet|ssc|banking",
]


class QualityWorker:
    """Evaluates study material candidates for structural validity, uniqueness, educational relevance, and completeness."""

    @staticmethod
    def is_valid_pdf_magic_bytes(header_bytes: bytes) -> bool:
        """Check if raw byte stream begins with standard %PDF- header."""
        return header_bytes.startswith(b"%PDF-")

    @staticmethod
    def check_educational_usefulness(title: str, text: str, page_count: int) -> Tuple[bool, str]:
        """Strictly distinguish genuine study material from administrative/procurement noise.

        Rejects:
        - Tenders / RFPs / Procurement notices (निविदा, RFP, Tender, Procurement)
        - Blank application forms / registration templates (अर्ज नमुना)
        - Staff transfers / seniority lists / administrative orders (बदली, ज्येष्ठता)
        - Meeting agendas / attendance lists without educational content.

        Accepts:
        - Syllabi, chapter notes, question banks, PYQs, solved papers, formula compendiums.
        - Educational and exam pattern guidelines.
        """
        combined = f"{title} {text[:1500]}".lower()

        # 1. Reject purely administrative noise
        for pattern in ADMINISTRATIVE_NOISE_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                # Exception: If document has strong educational markers (e.g. syllabus or PYQ attached)
                has_strong_edu = bool(re.search(r"अभ्यासक्रम|syllabus|question paper|प्रश्नपत्रिका", combined, re.IGNORECASE))
                if not has_strong_edu or page_count <= 2:
                    return False, f"Rejected administrative/procurement noise matching '{pattern}'"

        # 2. Require educational relevance signals
        has_edu_match = any(re.search(pat, combined, re.IGNORECASE) for pat in EDUCATIONAL_CONTENT_PATTERNS)
        if not has_edu_match and len(text.strip()) > 100:
            return False, "Rejected non-educational document (No syllabus, subject, or study keywords found)"

        return True, "Educational usefulness verified"

    def evaluate_candidate(
        self,
        doc: ProcessedDocument,
        title: str,
        existing_hashes: Optional[Set[str]] = None,
        existing_titles: Optional[List[str]] = None,
    ) -> Tuple[bool, str, int]:
        """Validate candidate document. Returns (is_approved, reason, quality_score)."""
        existing_hashes = existing_hashes or set()
        existing_titles = existing_titles or []

        # 1. Structural & Format Verification
        if not doc.is_valid:
            return False, f"Broken or non-PDF file: {doc.error_message}", 0

        if doc.file_size_bytes < 1024:  # Under 1 KB is an empty stub
            return False, "File too small (< 1KB) / Empty document", 0

        # 2. Educational Usefulness Check
        is_useful, edu_reason = self.check_educational_usefulness(
            title=title,
            text=doc.extracted_text,
            page_count=doc.page_count,
        )
        if not is_useful:
            return False, edu_reason, 0

        # 3. Binary SHA-256 Content Hash Deduplication
        if doc.content_hash and doc.content_hash in existing_hashes:
            return False, f"Duplicate content (SHA-256 match: {doc.content_hash[:8]}...)", 0

        # 4. Fuzzy Title Similarity Deduplication
        if existing_titles and title:
            match = process.extractOne(title, existing_titles, scorer=fuzz.ratio)
            if match:
                matched_title, score, _ = match
                if score >= 93:
                    return False, f"Duplicate title similarity ({score}% match with '{matched_title[:30]}...')", 0

        # 5. Quality Score Calculation (1 to 100)
        score = 70  # Baseline for valid readable educational PDF

        if doc.page_count >= 5:
            score += 10
        elif doc.page_count >= 1:
            score += 5

        if len(doc.extracted_text) >= 150:
            score += 10
        elif len(doc.extracted_text) >= 40:
            score += 5

        if doc.language in ("Marathi", "Bilingual", "English"):
            score += 10

        score = min(100, max(1, score))
        return True, "Quality and educational usefulness verified & approved", score
