"""Unit Tests for HARALE DIGITAL STUDY POINT PDF Watermarking Engine."""

import os
from pathlib import Path
import pytest
from reportlab.pdfgen import canvas
from pypdf import PdfReader
from services.pdf_watermark import apply_harale_branding_to_pdf, create_watermark_canvas


def create_test_dummy_pdf(filepath: str, num_pages: int = 3) -> str:
    """Helper to generate a clean synthetic multi-page PDF for test assertions."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    can = canvas.Canvas(filepath)
    for i in range(num_pages):
        can.drawString(100, 700, f"Spardha Notes Hub - Test Page {i + 1}")
        can.drawString(100, 650, "Sample Indian Polity & MPSC Syllabus Notes")
        can.showPage()
    can.save()
    return filepath


def test_create_watermark_canvas():
    """Verify in-memory watermark canvas overlay generation."""
    packet = create_watermark_canvas(
        page_width=595.27,  # A4 width in points
        page_height=841.89,  # A4 height in points
        brand_name="HARALE DIGITAL STUDY POINT",
        channel="@spardhanoteshub",
        bot_username="@SpardhaNotes_bot",
        is_first_page=True,
    )
    assert packet is not None
    assert packet.getbuffer().nbytes > 0

    reader = PdfReader(packet)
    assert len(reader.pages) == 1


def test_apply_harale_branding_to_pdf(tmp_path):
    """Verify end-to-end PDF watermarking and page structure preservation."""
    sample_in = str(tmp_path / "dummy_notes.pdf")
    sample_out = str(tmp_path / "dummy_notes_branded.pdf")

    create_test_dummy_pdf(sample_in, num_pages=3)
    assert os.path.exists(sample_in)

    branded_path = apply_harale_branding_to_pdf(
        input_pdf_path=sample_in,
        output_pdf_path=sample_out,
        brand_name="HARALE DIGITAL STUDY POINT",
        channel="@spardhanoteshub",
        bot_username="@SpardhaNotes_bot",
    )

    assert os.path.exists(branded_path)
    assert os.path.getsize(branded_path) > 0

    # Verify branded PDF integrity
    reader = PdfReader(branded_path)
    assert len(reader.pages) == 3


def test_watermark_non_existent_file():
    """Verify graceful handling for non-existent files."""
    with pytest.raises(FileNotFoundError):
        apply_harale_branding_to_pdf("/non/existent/path/document.pdf")
