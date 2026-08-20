"""Unit Tests for QualityWorker Deduplication & Quality Scoring."""

import pytest
from workers.processing_worker import ProcessedDocument
from workers.quality_worker import QualityWorker


def test_quality_worker_approves_valid_document():
    """Verify approval and high quality score for valid documents."""
    qw = QualityWorker()
    doc = ProcessedDocument(
        file_path="mock://test.pdf",
        content_hash="abc123hash",
        page_count=10,
        extracted_text="MPSC भारतीय राज्यघटना व प्रशासन सविस्तर मार्गदर्शक २०२४ " * 10,
        language="Marathi",
        detected_topic="राज्यघटना",
        detected_year=2024,
        file_size_bytes=50000,
        is_valid=True,
    )
    is_app, reason, score = qw.evaluate_candidate(
        doc=doc,
        title="MPSC राज्यघटना मार्गदर्शक",
        existing_hashes=set(),
        existing_titles=[],
    )
    assert is_app is True
    assert score >= 80


def test_quality_worker_rejects_content_hash_duplicate():
    """Verify rejection when identical SHA-256 binary hash exists."""
    qw = QualityWorker()
    doc = ProcessedDocument(
        file_path="mock://test2.pdf",
        content_hash="duplicate_sha256_hash",
        page_count=5,
        extracted_text="Sample Content",
        language="Marathi",
        detected_topic="General",
        detected_year=2024,
        file_size_bytes=20000,
        is_valid=True,
    )
    is_app, reason, score = qw.evaluate_candidate(
        doc=doc,
        title="Distinct Title",
        existing_hashes={"duplicate_sha256_hash"},
        existing_titles=[],
    )
    assert is_app is False
    assert "Duplicate content" in reason


def test_quality_worker_rejects_fuzzy_title_duplicate():
    """Verify rejection when title has >92% similarity with existing."""
    qw = QualityWorker()
    doc = ProcessedDocument(
        file_path="mock://test3.pdf",
        content_hash="unique_hash_999",
        page_count=5,
        extracted_text="Sample Content",
        language="Marathi",
        detected_topic="General",
        detected_year=2024,
        file_size_bytes=20000,
        is_valid=True,
    )
    is_app, reason, score = qw.evaluate_candidate(
        doc=doc,
        title="Maharashtra Police Bharti Ankganit Sarav Paper 2024",
        existing_hashes=set(),
        existing_titles=["Maharashtra Police Bharti Ankganit Sarav Paper 2024!"],
    )
    assert is_app is False
    assert "Duplicate title" in reason
