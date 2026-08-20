"""Topic Matrix & Multi-Dimensional Educational Content Metrics.

Stores, aggregates, and computes coverage dimensions across:
- Material count
- Unique sources
- Years covered
- Languages
- Material types present & missing
- Quality score average
- Weighted coverage percentage
- Launch readiness status
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from database.models import ExamCategory


class TopicStatus(str, Enum):
    READY = "READY"    # Coverage >= 80% & Key material types present
    WEAK = "WEAK"      # Coverage between 20% and 79%
    GAP = "GAP"        # Coverage < 20% or 0 materials


@dataclass
class TopicMetrics:
    topic_name: str
    subject_name: str
    exam_category: ExamCategory
    material_count: int = 0
    unique_sources: Set[str] = field(default_factory=set)
    years_covered: Set[int] = field(default_factory=set)
    languages: Set[str] = field(default_factory=set)
    material_types_present: Set[str] = field(default_factory=set)
    required_material_types: List[str] = field(default_factory=list)
    missing_material_types: List[str] = field(default_factory=list)
    quality_scores: List[float] = field(default_factory=list)
    quality_avg: float = 0.0
    coverage_pct: float = 0.0
    status: TopicStatus = TopicStatus.GAP
    material_ids: List[int] = field(default_factory=list)

    def calculate(self) -> None:
        """Compute average quality, missing material types, weighted coverage %, and status."""
        if self.quality_scores:
            self.quality_avg = round(sum(self.quality_scores) / len(self.quality_scores), 1)
        else:
            self.quality_avg = 0.0

        # Calculate missing required types
        present_lower = {t.lower() for t in self.material_types_present}
        self.missing_material_types = [
            req for req in self.required_material_types
            if req.lower() not in present_lower
        ]

        if not self.required_material_types:
            type_ratio = 1.0 if self.material_count > 0 else 0.0
        else:
            present_req_count = len(self.required_material_types) - len(self.missing_material_types)
            type_ratio = present_req_count / len(self.required_material_types)

        # Multi-dimensional weighted coverage formula
        # 1. Type Diversity (60% weight)
        # 2. Material Depth & Count (20% weight, saturated at 3 materials)
        # 3. Source & Year Diversity (10% weight)
        # 4. Average Quality Factor (10% weight)
        depth_ratio = min(self.material_count, 3) / 3.0
        source_ratio = min(len(self.unique_sources) + (1 if len(self.years_covered) > 0 else 0), 2) / 2.0
        quality_ratio = min(self.quality_avg, 100.0) / 100.0 if self.material_count > 0 else 0.0

        raw_coverage = (
            (type_ratio * 0.60) +
            (depth_ratio * 0.20) +
            (source_ratio * 0.10) +
            (quality_ratio * 0.10)
        ) * 100.0

        self.coverage_pct = round(min(raw_coverage, 100.0), 1)

        # Determine Topic Status
        if self.coverage_pct >= 80.0 and len(self.missing_material_types) == 0 and self.material_count >= 2:
            self.status = TopicStatus.READY
        elif self.material_count > 0 or self.coverage_pct >= 20.0:
            self.status = TopicStatus.WEAK
        else:
            self.status = TopicStatus.GAP

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic_name": self.topic_name,
            "subject_name": self.subject_name,
            "exam_category": self.exam_category.value,
            "material_count": self.material_count,
            "unique_sources": sorted(list(self.unique_sources)),
            "years_covered": sorted(list(self.years_covered)),
            "languages": sorted(list(self.languages)),
            "material_types_present": sorted(list(self.material_types_present)),
            "required_material_types": self.required_material_types,
            "missing_material_types": self.missing_material_types,
            "quality_avg": self.quality_avg,
            "coverage_pct": self.coverage_pct,
            "status": self.status.value,
            "material_ids": self.material_ids,
        }


@dataclass
class SubjectMetrics:
    subject_name: str
    exam_category: ExamCategory
    topic_metrics: List[TopicMetrics] = field(default_factory=list)
    total_materials: int = 0
    coverage_pct: float = 0.0
    status: TopicStatus = TopicStatus.GAP
    gap_count: int = 0
    weak_count: int = 0
    ready_count: int = 0

    def calculate(self) -> None:
        """Aggregate metrics across all child topics."""
        if not self.topic_metrics:
            self.coverage_pct = 0.0
            self.status = TopicStatus.GAP
            return

        for tm in self.topic_metrics:
            tm.calculate()

        unique_ids = set(mid for tm in self.topic_metrics for mid in tm.material_ids)
        if self.total_materials == 0:
            self.total_materials = len(unique_ids)

        self.coverage_pct = round(
            sum(tm.coverage_pct for tm in self.topic_metrics) / len(self.topic_metrics), 1
        )
        self.gap_count = sum(1 for tm in self.topic_metrics if tm.status == TopicStatus.GAP)
        self.weak_count = sum(1 for tm in self.topic_metrics if tm.status == TopicStatus.WEAK)
        self.ready_count = sum(1 for tm in self.topic_metrics if tm.status == TopicStatus.READY)

        if self.coverage_pct >= 75.0 and self.gap_count == 0:
            self.status = TopicStatus.READY
        elif self.total_materials > 0 or len(unique_ids) > 0:
            self.status = TopicStatus.WEAK
        else:
            self.status = TopicStatus.GAP

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject_name": self.subject_name,
            "exam_category": self.exam_category.value,
            "total_materials": self.total_materials,
            "coverage_pct": self.coverage_pct,
            "status": self.status.value,
            "gap_count": self.gap_count,
            "weak_count": self.weak_count,
            "ready_count": self.ready_count,
            "topics": [t.to_dict() for t in self.topic_metrics],
        }


@dataclass
class ExamMetrics:
    exam_category: ExamCategory
    display_name: str
    authority: str
    subject_metrics: List[SubjectMetrics] = field(default_factory=list)
    total_materials: int = 0
    overall_coverage_pct: float = 0.0
    is_ready: bool = False
    readiness_threshold: float = 80.0
    total_topics: int = 0
    ready_topics: int = 0
    weak_topics: int = 0
    gap_topics: int = 0

    def calculate(self) -> None:
        """Aggregate metrics across all subjects and determine strict launch readiness."""
        if not self.subject_metrics:
            self.overall_coverage_pct = 0.0
            self.is_ready = False
            return

        for sm in self.subject_metrics:
            sm.calculate()

        if self.total_materials == 0:
            self.total_materials = sum(sm.total_materials for sm in self.subject_metrics)

        self.overall_coverage_pct = round(
            sum(sm.coverage_pct for sm in self.subject_metrics) / len(self.subject_metrics), 1
        )

        all_topics = [tm for sm in self.subject_metrics for tm in sm.topic_metrics]
        self.total_topics = len(all_topics)
        self.ready_topics = sum(1 for tm in all_topics if tm.status == TopicStatus.READY)
        self.weak_topics = sum(1 for tm in all_topics if tm.status == TopicStatus.WEAK)
        self.gap_topics = sum(1 for tm in all_topics if tm.status == TopicStatus.GAP)

        # STRICT READINESS RULE:
        # An exam is NEVER marked ready based on PDF count alone.
        # It is READY only when:
        # 1. overall_coverage_pct >= readiness_threshold (default 80%)
        # 2. gap_topics == 0 (Zero complete syllabus holes)
        # 3. Every subject has coverage >= 60%
        has_subject_coverage = all(sm.coverage_pct >= 60.0 for sm in self.subject_metrics)
        self.is_ready = (
            self.overall_coverage_pct >= self.readiness_threshold
            and self.gap_topics == 0
            and has_subject_coverage
            and self.total_materials > 0
        )


    def to_dict(self) -> Dict[str, Any]:
        return {
            "exam_category": self.exam_category.value,
            "display_name": self.display_name,
            "authority": self.authority,
            "total_materials": self.total_materials,
            "overall_coverage_pct": self.overall_coverage_pct,
            "is_ready": self.is_ready,
            "readiness_threshold": self.readiness_threshold,
            "total_topics": self.total_topics,
            "ready_topics": self.ready_topics,
            "weak_topics": self.weak_topics,
            "gap_topics": self.gap_topics,
            "subjects": [s.to_dict() for s in self.subject_metrics],
        }


@dataclass
class CoverageMatrix:
    exam_matrices: Dict[ExamCategory, ExamMetrics] = field(default_factory=dict)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    total_catalog_materials: int = 0
    overall_platform_coverage_pct: float = 0.0
    ready_exam_count: int = 0

    def calculate(self) -> None:
        """Aggregate platform-level metrics."""
        for em in self.exam_matrices.values():
            em.calculate()

        if self.exam_matrices:
            self.total_catalog_materials = sum(em.total_materials for em in self.exam_matrices.values())
            self.overall_platform_coverage_pct = round(
                sum(em.overall_coverage_pct for em in self.exam_matrices.values()) / len(self.exam_matrices), 1
            )
            self.ready_exam_count = sum(1 for em in self.exam_matrices.values() if em.is_ready)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "total_catalog_materials": self.total_catalog_materials,
            "overall_platform_coverage_pct": self.overall_platform_coverage_pct,
            "ready_exam_count": self.ready_exam_count,
            "total_exams": len(self.exam_matrices),
            "exams": {k.value: v.to_dict() for k, v in self.exam_matrices.items()},
        }
