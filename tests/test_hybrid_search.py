"""Unit Tests for Hybrid AI Search Engine & Reciprocal Rank Fusion."""

import pytest
from database.models import ExamCategory, MaterialType, StudyMaterial
from search_engine.hybrid_search import compute_cosine_similarity, rank_hybrid_materials
from database.crud import expand_bilingual_terms


def test_cosine_similarity_math():
    """Verify vector cosine similarity calculation."""
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [1.0, 0.0, 0.0]
    assert compute_cosine_similarity(vec1, vec2) == pytest.approx(1.0)

    vec3 = [0.0, 1.0, 0.0]
    assert compute_cosine_similarity(vec1, vec3) == pytest.approx(0.0)

    # Empty / mismatched length
    assert compute_cosine_similarity([], [1.0]) == 0.0
    assert compute_cosine_similarity([1.0], [1.0, 2.0]) == 0.0


@pytest.mark.asyncio
async def test_rank_hybrid_materials_lexical():
    """Verify hybrid ranking accurately promotes top match via RRF."""
    mat1 = StudyMaterial(
        id=1,
        title="JEE Main Physics Formula & Quick Revision Handbook",
        exam_category=ExamCategory.JEE,
        subject="Physics",
        material_type=MaterialType.SHORT_NOTES,
        file_path="https://example.com/jee.pdf",
        year=2024,
    )
    mat2 = StudyMaterial(
        id=2,
        title="MPSC Maharashtra History & Social Reformers",
        exam_category=ExamCategory.MPSC,
        subject="History",
        material_type=MaterialType.SHORT_NOTES,
        file_path="https://example.com/mpsc.pdf",
        year=2024,
    )

    candidates = [mat2, mat1]
    expanded_terms = expand_bilingual_terms("JEE Physics")

    ranked = await rank_hybrid_materials(
        query="JEE Physics",
        candidates=candidates,
        expanded_terms=expanded_terms,
        api_key=None,  # Tests lexical + RRF fallback path
    )

    assert len(ranked) == 2
    assert ranked[0].id == 1  # JEE physics should be #1
    assert ranked[0].exam_category == ExamCategory.JEE


def test_expanded_synonyms():
    """Verify new exam clusters expand correctly."""
    terms_upsc = expand_bilingual_terms("upsc prelims")
    assert "civil services" in terms_upsc or "ias" in terms_upsc

    terms_neet = expand_bilingual_terms("neet biology")
    assert "medical" in terms_neet or "biology" in terms_neet

    terms_board = expand_bilingual_terms("10th board")
    assert "ssc 10th" in terms_board or "state board" in terms_board
