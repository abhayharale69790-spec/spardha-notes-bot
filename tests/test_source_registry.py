"""Unit Tests for SourceRegistry & Dynamic Source Discovery."""

import pytest
from database.models import ExamCategory, MaterialType
from services.source_registry import (
    SourceRegistry,
    RegisteredSource,
    SourceType,
    DEFAULT_REGISTERED_SOURCES,
)


def test_default_sources_registry_coverage():
    """Verify default sources cover all critical exam categories."""
    reg = SourceRegistry()
    sources = reg.get_all_sources(enabled_only=True)
    assert len(sources) >= 10

    categories = {s.exam_category for s in sources}
    assert ExamCategory.MPSC in categories
    assert ExamCategory.UPSC in categories
    assert ExamCategory.POLICE_BHARTI in categories
    assert ExamCategory.JEE in categories
    assert ExamCategory.NEET in categories
    assert ExamCategory.BOARD_10_12 in categories
    assert ExamCategory.NCERT in categories
    assert ExamCategory.BANKING in categories
    assert ExamCategory.SSC in categories


def test_source_filtering_and_lookup():
    """Verify source retrieval by ID and by category."""
    reg = SourceRegistry()
    mpsc_sources = reg.get_sources_by_category(ExamCategory.MPSC)
    assert len(mpsc_sources) >= 1
    assert any("mpsc" in s.source_id for s in mpsc_sources)

    src = reg.get_source_by_id("mpsc_announcements_portal")
    assert src is not None
    assert src.name == "MPSC Maharashtra Public Service Commission"


def test_dynamic_source_registration_and_disable():
    """Verify adding custom sources and toggling enabled flag."""
    reg = SourceRegistry()
    custom_src = RegisteredSource(
        source_id="custom_test_drive",
        name="Custom Test Study Drive",
        source_type=SourceType.GDRIVE,
        url="https://drive.google.com/test",
        exam_category=ExamCategory.GENERAL,
        default_subject="Test Subject",
        default_material_type=MaterialType.SHORT_NOTES,
    )
    reg.register_source(custom_src)
    assert reg.get_source_by_id("custom_test_drive") is not None

    reg.disable_source("custom_test_drive")
    enabled = reg.get_all_sources(enabled_only=True)
    assert not any(s.source_id == "custom_test_drive" for s in enabled)
