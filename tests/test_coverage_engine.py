"""Comprehensive Unit and Integration Tests for Syllabus-Driven Content Coverage Engine."""

import pytest
import pytest_asyncio
from database.models import ExamCategory, MaterialType, StudyMaterial
from database.session import get_session, init_db
from database import crud
from services.syllabus_registry import (
    ExamSyllabus,
    get_all_syllabi,
    get_exam_syllabus,
    SYLLABUS_REGISTRY,
    ContentMaterialType,
)
from services.topic_matrix import (
    CoverageMatrix,
    ExamMetrics,
    SubjectMetrics,
    TopicMetrics,
    TopicStatus,
)
from services.coverage_engine import (
    coverage_engine,
    map_material_type_to_syllabus_type,
    score_material_topic_match,
)
from services.gap_detector import gap_detector, TargetedHarvestJob
from services.coverage_report import (
    generate_console_coverage_report,
    format_telegram_overview_card,
    format_telegram_exam_drilldown_card,
    render_progress_bar,
)
from bot.handlers.coverage import build_overview_keyboard, build_exam_drilldown_keyboard


@pytest.mark.asyncio
async def test_syllabus_registry_coverage():
    """Verify all 10 official exam syllabi are present with detailed subject/topic trees."""
    syllabi = get_all_syllabi()
    assert len(syllabi) == 10

    for s in syllabi:
        assert len(s.subjects) >= 2, f"{s.display_name} must have at least 2 subjects"
        assert s.min_readiness_threshold >= 75.0
        for subj in s.subjects:
            assert len(subj.topics) >= 2, f"{subj.name} must have at least 2 topics"
            for t in subj.topics:
                assert len(t.required_types) >= 2
                assert len(t.keywords) >= 2


def test_progress_bar_rendering():
    """Verify ASCII progress bar formatting across boundary values."""
    assert render_progress_bar(0.0, 10) == "░░░░░░░░░░"
    assert render_progress_bar(50.0, 10) == "▓▓▓▓▓░░░░░"
    assert render_progress_bar(100.0, 10) == "▓▓▓▓▓▓▓▓▓▓"


def test_topic_metrics_calculation_and_status():
    """Test multi-dimensional coverage metric computation on a topic node."""
    tm = TopicMetrics(
        topic_name="भारतीय राज्यघटना व निर्मिती",
        subject_name="राज्यशास्त्र (Polity)",
        exam_category=ExamCategory.MPSC,
        required_material_types=["NOTES", "PYQ", "PRACTICE_TEST"],
    )
    tm.calculate()
    assert tm.status == TopicStatus.GAP
    assert tm.coverage_pct == 0.0
    assert len(tm.missing_material_types) == 3

    # Add materials covering all types
    tm.material_count = 3
    tm.unique_sources = {"MPSC Portal", "Harale Study Point"}
    tm.years_covered = {2023, 2024}
    tm.languages = {"Marathi", "English"}
    tm.material_types_present = {"NOTES", "PYQ", "PRACTICE_TEST"}
    tm.quality_scores = [95.0, 90.0, 100.0]

    tm.calculate()
    assert tm.status == TopicStatus.READY
    assert tm.coverage_pct >= 85.0
    assert len(tm.missing_material_types) == 0
    assert tm.quality_avg == 95.0


def test_exam_metrics_strict_readiness():
    """Verify an exam is NEVER marked ready based only on material count."""
    em = ExamMetrics(
        exam_category=ExamCategory.MPSC,
        display_name="MPSC",
        authority="MPSC",
        readiness_threshold=80.0,
    )

    # Scenario 1: Many materials but large syllabus gaps -> MUST NOT BE READY
    sm = SubjectMetrics(subject_name="Polity", exam_category=ExamCategory.MPSC)
    tm1 = TopicMetrics(
        topic_name="Topic 1", subject_name="Polity", exam_category=ExamCategory.MPSC,
        material_count=50, material_types_present={"NOTES"}, required_material_types=["NOTES", "PYQ"],
    )
    tm2 = TopicMetrics(
        topic_name="Topic 2", subject_name="Polity", exam_category=ExamCategory.MPSC,
        material_count=0, required_material_types=["NOTES", "PYQ"],  # Complete GAP
    )
    sm.topic_metrics = [tm1, tm2]
    em.subject_metrics = [sm]

    em.calculate()
    assert em.is_ready is False
    assert em.gap_topics > 0


@pytest.mark.asyncio
async def test_coverage_engine_execution():
    """Test full coverage engine calculation on live database."""
    await init_db()
    matrix = await coverage_engine.compute_coverage_matrix()

    assert matrix is not None
    assert len(matrix.exam_matrices) == 10
    assert matrix.overall_platform_coverage_pct >= 0.0

    # Ensure each exam category metric is populated
    for cat in ExamCategory:
        if cat in SYLLABUS_REGISTRY:
            em = matrix.exam_matrices.get(cat)
            assert em is not None
            assert len(em.subject_metrics) > 0


@pytest.mark.asyncio
async def test_gap_detector_and_targeted_harvest():
    """Verify gap detector detects missing nodes and generates prioritized harvest jobs."""
    matrix = await coverage_engine.compute_coverage_matrix()
    jobs = gap_detector.detect_gaps_from_matrix(matrix)

    assert isinstance(jobs, list)
    if jobs:
        first_job = jobs[0]
        assert first_job.job_id.startswith(("gap_", "weak_"))
        assert len(first_job.search_keywords) >= 3
        assert first_job.priority in (1, 2)


def test_coverage_reports_generation():
    """Verify console and Telegram card formatters generate clean HTML/text."""
    matrix = CoverageMatrix()
    matrix.overall_platform_coverage_pct = 78.5
    matrix.total_catalog_materials = 35
    matrix.ready_exam_count = 4

    em = ExamMetrics(
        exam_category=ExamCategory.MPSC,
        display_name="MPSC Rajyaseva",
        authority="MPSC",
        overall_coverage_pct=85.0,
        total_materials=12,
        is_ready=True,
    )
    sm = SubjectMetrics(
        subject_name="Polity",
        exam_category=ExamCategory.MPSC,
        coverage_pct=90.0,
        total_materials=6,
    )
    tm = TopicMetrics(
        topic_name="Fundamental Rights",
        subject_name="Polity",
        exam_category=ExamCategory.MPSC,
        material_count=3,
        coverage_pct=95.0,
        status=TopicStatus.READY,
    )
    sm.topic_metrics = [tm]
    em.subject_metrics = [sm]
    matrix.exam_matrices[ExamCategory.MPSC] = em

    console_report = generate_console_coverage_report(matrix)
    assert "SYLLABUS-DRIVEN CONTENT COVERAGE DASHBOARD" in console_report
    assert "MPSC" in console_report

    tg_overview = format_telegram_overview_card(matrix)
    assert "<b>अभ्यासक्रम घटक निहाय कव्हरेज अहवाल" in tg_overview
    assert "78.5%" in tg_overview

    tg_drilldown = format_telegram_exam_drilldown_card(em)
    assert "MPSC Rajyaseva" in tg_drilldown
    assert "Polity" in tg_drilldown


def test_telegram_keyboard_builders():
    """Verify Telegram inline keyboards for coverage navigation."""
    kb_overview = build_overview_keyboard()
    assert len(kb_overview.inline_keyboard) == 6

    kb_drilldown = build_exam_drilldown_keyboard("MPSC")
    assert len(kb_drilldown.inline_keyboard) == 2
