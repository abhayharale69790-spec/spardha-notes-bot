"""Indexing Worker: End-to-End Ingestion, Quality Validation & Database Storage Pipeline."""

from dataclasses import dataclass
import logging
from typing import List, Optional, Set
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import StudyMaterial
from database import crud
from workers.harvest_worker import HarvestCandidate
from workers.processing_worker import ProcessingWorker
from workers.quality_worker import QualityWorker

logger = logging.getLogger(__name__)


@dataclass
class IngestionSummary:
    """Consolidated summary results for an ingestion run."""
    sources_scanned: int = 0
    files_scanned: int = 0
    files_downloaded: int = 0
    files_processed: int = 0
    duplicates_detected: int = 0
    failures_count: int = 0
    files_indexed: int = 0


class IndexingWorker:
    """Coordinates processing, deduplication, quality scoring, and storage into StudyMaterial."""

    def __init__(
        self,
        processing_worker: Optional[ProcessingWorker] = None,
        quality_worker: Optional[QualityWorker] = None,
    ) -> None:
        self.processor = processing_worker or ProcessingWorker()
        self.quality = quality_worker or QualityWorker()

    async def ingest_candidates(
        self,
        session: AsyncSession,
        candidates: List[HarvestCandidate],
    ) -> IngestionSummary:
        """Process, validate, deduplicate, and index a batch of harvested candidates."""
        summary = IngestionSummary(files_scanned=len(candidates))

        # 1. Fetch existing hashes and titles from database for deduplication
        existing_hashes_stmt = select(StudyMaterial.content_hash).where(StudyMaterial.content_hash.is_not(None))
        res_hashes = await session.execute(existing_hashes_stmt)
        existing_hashes: Set[str] = {row[0] for row in res_hashes.all() if row[0]}

        existing_titles_stmt = select(StudyMaterial.title)
        res_titles = await session.execute(existing_titles_stmt)
        existing_titles: List[str] = [row[0] for row in res_titles.all() if row[0]]

        sources_seen: Set[str] = set()

        for cand in candidates:
            sources_seen.add(cand.source_id)

            # Check exact title match before download to save bandwidth
            if cand.title in existing_titles:
                summary.duplicates_detected += 1
                continue

            try:
                # 2. Download and extract text/metadata
                doc = await self.processor.download_and_process(
                    url=cand.url,
                    title=cand.title,
                    default_subject=cand.subject,
                )
                summary.files_downloaded += 1
                summary.files_processed += 1

                # 3. Quality evaluation and hash/similarity deduplication
                is_approved, reason, quality_score = self.quality.evaluate_candidate(
                    doc=doc,
                    title=cand.title,
                    existing_hashes=existing_hashes,
                    existing_titles=existing_titles,
                )

                if not is_approved:
                    if "Duplicate" in reason:
                        summary.duplicates_detected += 1
                    else:
                        summary.failures_count += 1
                        logger.warning(f"Candidate '{cand.title[:30]}' rejected: {reason}")
                    continue

                # 4. Store in StudyMaterial
                final_topic = doc.detected_topic or cand.subject
                final_lang = doc.language or cand.language
                final_year = doc.detected_year or cand.year

                await crud.create_study_material(
                    session=session,
                    title=cand.title,
                    exam_category=cand.exam_category,
                    subject=cand.subject,
                    material_type=cand.material_type,
                    file_path=cand.url,
                    year=final_year,
                    topic=final_topic,
                    language=final_lang,
                    source_name=cand.source_name,
                    content_hash=doc.content_hash,
                    extracted_text=doc.extracted_text,
                    quality_score=quality_score,
                    status="VERIFIED",
                )

                # Add to local cache for subsequent items in same batch
                if doc.content_hash:
                    existing_hashes.add(doc.content_hash)
                existing_titles.append(cand.title)
                summary.files_indexed += 1

            except Exception as e:
                summary.failures_count += 1
                logger.error(f"Error indexing candidate {cand.title}: {e}")

        summary.sources_scanned = len(sources_seen)

        # 5. Record telemetry in IngestionMetric
        if sources_seen:
            await crud.record_ingestion_metric(
                session=session,
                source_id="multi_harvest_batch",
                source_name=f"Harvest Batch ({len(sources_seen)} sources)",
                source_type="PORTAL",
                files_scanned=summary.files_scanned,
                files_downloaded=summary.files_downloaded,
                files_processed=summary.files_processed,
                duplicates_detected=summary.duplicates_detected,
                failures_count=summary.failures_count,
                status="SUCCESS" if summary.files_indexed > 0 else "PARTIAL",
                details=f"Indexed {summary.files_indexed} verified study materials.",
            )

        return summary
