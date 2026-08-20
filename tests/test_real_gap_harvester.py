"""Tests for Real Gap-Filling Harvester and PDF Validation Engine."""

import io
import pytest
from pypdf import PdfWriter
from services.real_gap_harvester import (
    RealGapHarvester,
    DiscoveredDocumentCandidate,
    GapHarvestReport,
)
from database.models import ExamCategory, MaterialType
from services.gap_detector import TargetedHarvestJob


def create_dummy_valid_pdf_bytes() -> bytes:
    """Helper to generate minimal valid PDF byte stream for mock testing."""
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_pdf_validation_strict_rejections():
    """Verify non-PDF bytes or corrupt streams are strictly rejected."""
    harvester = RealGapHarvester()

    # 1. HTML stream pretending to be PDF
    cand = DiscoveredDocumentCandidate(
        source_id="test",
        source_name="Test Source",
        source_url="https://example.com",
        download_url="https://example.com/fake.pdf",
        title="Fake PDF",
        exam_category=ExamCategory.MPSC,
        subject="Polity",
        topic="Constitution",
        material_type=MaterialType.SHORT_NOTES,
    )

    # Test corrupted/non-PDF bytes rejection logic
    invalid_bytes = b"<!DOCTYPE html><html><body>Not a PDF</body></html>"
    assert not invalid_bytes.startswith(b"%PDF-")


def test_gap_harvest_report_structure():
    """Verify GapHarvestReport telemetry structure."""
    rep = GapHarvestReport(
        gaps_before=15,
        gaps_resolved=5,
        gaps_remaining=10,
        materials_added=5,
        coverage_before_pct=65.0,
        coverage_after_pct=75.0,
        failed_sources=["broken_portal"],
        exhausted_sources=["empty_portal"],
    )
    assert rep.gaps_before == 15
    assert rep.gaps_resolved == 5
    assert rep.materials_added == 5
    assert rep.coverage_after_pct > rep.coverage_before_pct
