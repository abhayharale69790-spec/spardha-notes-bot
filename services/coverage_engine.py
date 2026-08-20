"""Syllabus Coverage Engine & Semantic Material Mapping Service.

Maps verified and indexed materials to the official examination syllabus tree using
multi-attribute content analysis (subject, topic tags, extracted text, metadata, material type).
Calculates live multi-dimensional coverage matrices and assesses strict launch readiness.
"""

import asyncio
from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import ExamCategory, MaterialType, StudyMaterial
from database.session import get_session, init_db
from database import crud
from services.syllabus_registry import (
    ExamSyllabus,
    SubjectNode,
    TopicNode,
    SubtopicNode,
    get_all_syllabi,
    get_exam_syllabus,
)
from services.topic_matrix import (
    CoverageMatrix,
    ExamMetrics,
    SubjectMetrics,
    TopicMetrics,
    TopicStatus,
)

logger = logging.getLogger(__name__)


def map_material_type_to_syllabus_type(mat_type: MaterialType) -> str:
    """Map internal database MaterialType to syllabus ContentMaterialType."""
    mapping = {
        MaterialType.SHORT_NOTES: "NOTES",
        MaterialType.PYQ: "PYQ",
        MaterialType.TEST_PAPER: "PRACTICE_TEST",
        MaterialType.CURRENT_AFFAIRS: "CURRENT_AFFAIRS",
        MaterialType.GR: "REFERENCE",
        MaterialType.SYLLABUS: "REFERENCE",
    }
    return mapping.get(mat_type, "NOTES")



def score_material_topic_match(material: StudyMaterial, topic: TopicNode, subject: SubjectNode) -> float:
    """Calculate multi-attribute match confidence score between material and a syllabus topic.

    Does NOT rely on title matching alone. Inspects:
    1. Direct subject and topic metadata fields (weight 40%)
    2. Extracted text and syllabus content snippets (weight 35%)
    3. Topic and subtopic keyword hits (weight 15%)
    4. Title token overlap (weight 10%)
    """
    score = 0.0

    mat_subject = (material.subject or "").lower()
    mat_topic = (material.topic or "").lower()
    mat_title = (material.title or "").lower()
    mat_text = (material.extracted_text or "").lower()

    topic_name = topic.name.lower()
    subject_name = subject.name.lower()

    # 1. Direct Subject & Topic metadata alignment
    if subject_name in mat_subject or any(kw in mat_subject for kw in subject.keywords):
        score += 25.0
    if topic_name in mat_topic or any(kw in mat_topic for kw in topic.keywords):
        score += 20.0

    # 2. Extracted Text & Content Analysis
    if mat_text:
        text_hits = sum(1 for kw in topic.keywords if kw.lower() in mat_text)
        if text_hits > 0:
            score += min(text_hits * 10.0, 30.0)

        # Check subtopics in text
        for sub in topic.subtopics:
            if sub.name.lower() in mat_text or any(skw.lower() in mat_text for skw in sub.keywords):
                score += 10.0
                break

    # 3. Keyword Analysis
    kw_hits = sum(1 for kw in topic.keywords if kw.lower() in mat_title or kw.lower() in mat_topic)
    if kw_hits > 0:
        score += min(kw_hits * 8.0, 15.0)

    # 4. Title tokens
    if topic_name in mat_title:
        score += 10.0

    return score


def _get_best_subject_for_material(mat: StudyMaterial, subjects: List[SubjectNode]) -> str:
    """Determine which official syllabus subject node this verified material primarily belongs to."""
    if not subjects:
        return ""
    clean_subj = (mat.subject or "").lower()
    clean_title = (mat.title or "").lower()

    best_match = subjects[0].name
    best_score = -1.0

    for sn in subjects:
        score = 0.0
        sn_clean = sn.name.lower()
        if sn_clean in clean_subj or clean_subj in sn_clean:
            score += 100.0
        for kw in sn.keywords:
            if kw.lower() in clean_subj:
                score += 50.0
            elif kw.lower() in clean_title:
                score += 20.0
        if score > best_score:
            best_score = score
            best_match = sn.name

    return best_match


class CoverageEngine:
    """Evaluates multi-dimensional curriculum coverage and provides readiness signals."""

    def __init__(self):
        self._cached_matrix: Optional[CoverageMatrix] = None
        self._last_evaluated_at: Optional[datetime] = None

    async def compute_coverage_matrix(
        self,
        session: Optional[AsyncSession] = None,
        force_refresh: bool = True,
    ) -> CoverageMatrix:
        """Compute the full curriculum coverage matrix across all 10 exam categories."""
        if not force_refresh and self._cached_matrix and self._last_evaluated_at:
            age = (datetime.now(timezone.utc) - self._last_evaluated_at).total_seconds()
            if age < 300:  # 5 min cache
                return self._cached_matrix

        if session is None:
            async with get_session() as auto_session:
                return await self._evaluate_with_session(auto_session)
        return await self._evaluate_with_session(session)


    async def _evaluate_with_session(self, session: AsyncSession) -> CoverageMatrix:
        """Internal evaluator executing queries with an active session."""
        # Fetch strictly VERIFIED materials
        stmt = select(StudyMaterial).where(StudyMaterial.status == "VERIFIED")
        result = await session.execute(stmt)
        materials = result.scalars().all()

        logger.info(f"Computing syllabus coverage across {len(materials)} verified materials...")

        matrix = CoverageMatrix()
        syllabi = get_all_syllabi()

        for syllabus in syllabi:
            cat = syllabus.exam_category
            exam_mats = [m for m in materials if m.exam_category == cat]

            exam_metric = ExamMetrics(
                exam_category=cat,
                display_name=syllabus.display_name,
                authority=syllabus.authority,
                readiness_threshold=syllabus.min_readiness_threshold,
                total_materials=len(exam_mats),
            )

            # Map each material in exam_mats to its best subject
            subj_materials_map = {sn.name: [] for sn in syllabus.subjects}
            for mat in exam_mats:
                best_sname = _get_best_subject_for_material(mat, syllabus.subjects)
                if best_sname in subj_materials_map:
                    subj_materials_map[best_sname].append(mat)
                elif syllabus.subjects:
                    subj_materials_map[syllabus.subjects[0].name].append(mat)

            for subj_node in syllabus.subjects:
                subj_mats = subj_materials_map.get(subj_node.name, [])
                subj_metric = SubjectMetrics(
                    subject_name=subj_node.name,
                    exam_category=cat,
                    total_materials=len(subj_mats),
                )

                for topic_node in subj_node.topics:
                    req_types = [t.value for t in topic_node.required_types]
                    t_metric = TopicMetrics(
                        topic_name=topic_node.name,
                        subject_name=subj_node.name,
                        exam_category=cat,
                        required_material_types=req_types,
                    )

                    # Match materials to this topic
                    for mat in subj_mats:
                        match_score = score_material_topic_match(mat, topic_node, subj_node)
                        # Significant multi-attribute match threshold
                        if match_score >= 25.0:
                            t_metric.material_count += 1
                            t_metric.material_ids.append(mat.id)
                            if mat.source_name:
                                t_metric.unique_sources.add(mat.source_name)
                            if mat.year:
                                t_metric.years_covered.add(mat.year)
                            if mat.language:
                                t_metric.languages.add(mat.language)

                            mapped_type = map_material_type_to_syllabus_type(mat.material_type)
                            t_metric.material_types_present.add(mapped_type)
                            t_metric.quality_scores.append(float(mat.quality_score or 85.0))

                    t_metric.calculate()
                    subj_metric.topic_metrics.append(t_metric)

                subj_metric.calculate()
                exam_metric.subject_metrics.append(subj_metric)

            exam_metric.calculate()
            matrix.exam_matrices[cat] = exam_metric

        matrix.calculate()

        self._cached_matrix = matrix
        self._last_evaluated_at = datetime.now(timezone.utc)
        return matrix


    async def get_exam_coverage(self, exam_category: ExamCategory) -> Optional[ExamMetrics]:
        """Get live or cached coverage metrics for a specific exam category."""
        if not self._cached_matrix:
            await self.compute_coverage_matrix()
        return self._cached_matrix.exam_matrices.get(exam_category) if self._cached_matrix else None

    async def get_cached_matrix(self) -> CoverageMatrix:
        """Return cached coverage matrix, computing on-the-fly if needed."""
        if not self._cached_matrix:
            return await self.compute_coverage_matrix()
        return self._cached_matrix


# Singleton Engine Instance
coverage_engine = CoverageEngine()
