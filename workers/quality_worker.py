"""Quality Worker: PDF Magic Header Validation, Strict Deduplication & Quality Scoring."""

import logging
from typing import List, Optional, Set, Tuple
from rapidfuzz import fuzz, process
from workers.processing_worker import ProcessedDocument

logger = logging.getLogger(__name__)


class QualityWorker:
    """Evaluates study material candidates for structural validity, uniqueness, and completeness."""

    @staticmethod
    def is_valid_pdf_magic_bytes(header_bytes: bytes) -> bool:
        """Check if raw byte stream begins with standard %PDF- header."""
        return header_bytes.startswith(b"%PDF-")

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

        # 2. Binary SHA-256 Content Hash Deduplication
        if doc.content_hash and doc.content_hash in existing_hashes:
            return False, f"Duplicate content (SHA-256 match: {doc.content_hash[:8]}...)", 0

        # 3. Fuzzy Title Similarity Deduplication
        if existing_titles and title:
            match = process.extractOne(title, existing_titles, scorer=fuzz.ratio)
            if match:
                matched_title, score, _ = match
                if score >= 93:
                    return False, f"Duplicate title similarity ({score}% match with '{matched_title[:30]}...')", 0

        # 4. Quality Score Calculation (1 to 100)
        score = 70  # Baseline for valid readable PDF

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
        return True, "Quality verified & approved", score
