"""Unit Tests for ProcessingWorker PDF Extraction, SHA256 & Language Detection."""

import io
import pytest
from reportlab.pdfgen import canvas
from workers.processing_worker import ProcessingWorker, ProcessedDocument


def create_sample_pdf_bytes(text_content: str = "Sample Text", num_pages: int = 1) -> bytes:
    """Helper to generate in-memory valid PDF bytes."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for _ in range(num_pages):
        c.drawString(100, 750, text_content)
        c.showPage()
    c.save()
    return buf.getvalue()


def test_sha256_computation():
    """Verify SHA-256 binary hash computation."""
    data = b"%PDF-1.4 test stream"
    h1 = ProcessingWorker.compute_sha256(data)
    assert len(h1) == 64
    assert h1 == ProcessingWorker.compute_sha256(data)


def test_language_and_topic_detection():
    """Verify Devanagari Marathi and topic classification."""
    marathi_text = "महाराष्ट्र शासन निर्णय आणि पोलीस भरती परीक्षा २०२४"
    lang_mr = ProcessingWorker.detect_language(marathi_text)
    assert lang_mr == "Marathi"

    topic_polity = ProcessingWorker.detect_topic(
        title="MPSC भारतीय संविधान व राज्यघटना",
        text="मूलभूत हक्क आणि मार्गदर्शक तत्वे",
    )
    assert "संविधान" in topic_polity or "राज्यघटना" in topic_polity

    english_text = "NTA JEE Main Physics Formula Compendium 2024"
    lang_en = ProcessingWorker.detect_language(english_text)
    assert lang_en == "English"


def test_process_valid_pdf_bytes():
    """Verify parsing valid in-memory PDF stream."""
    worker = ProcessingWorker()
    pdf_bytes = create_sample_pdf_bytes("महाराष्ट्र पोलीस भरती गणित सराव पेपर 2024", num_pages=3)
    doc = worker.process_pdf_bytes(
        content=pdf_bytes,
        file_path="mock://police.pdf",
        title="पोलीस भरती गणित",
        default_subject="गणित",
    )
    assert doc.is_valid is True
    assert doc.page_count == 3
    assert len(doc.content_hash) == 64
    assert doc.file_size_bytes > 0


def test_process_invalid_magic_bytes():
    """Verify rejection of non-PDF HTML or plain text."""
    worker = ProcessingWorker()
    bad_bytes = b"<html><head><title>404 Not Found</title></head></html>"
    doc = worker.process_pdf_bytes(
        content=bad_bytes,
        file_path="mock://error.html",
        title="Error Page",
    )
    assert doc.is_valid is False
    assert "magic bytes" in doc.error_message
