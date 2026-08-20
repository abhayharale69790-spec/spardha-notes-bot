"""Harvest Worker: Autonomous Web, Portal, and Cloud Source Harvester."""

from dataclasses import dataclass
import logging
import re
from typing import List, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from database.models import ExamCategory, MaterialType
from scraper.client import ResilientHttpClient
from services.source_registry import RegisteredSource, SourceRegistry, source_registry

logger = logging.getLogger(__name__)


@dataclass
class HarvestCandidate:
    """Discovered candidate material from a registered source."""
    source_id: str
    source_name: str
    title: str
    url: str
    exam_category: ExamCategory
    subject: str
    material_type: MaterialType
    year: Optional[int] = 2024
    language: str = "Marathi"


class HarvestWorker:
    """Coordinates autonomous multi-source harvesting across all registered educational repositories."""

    def __init__(
        self,
        registry: Optional[SourceRegistry] = None,
        http_client: Optional[ResilientHttpClient] = None,
    ) -> None:
        self.registry = registry or source_registry
        self.client = http_client or ResilientHttpClient()

    async def harvest_source(self, source: RegisteredSource) -> List[HarvestCandidate]:
        """Harvest candidate document links from a single registered source."""
        logger.info(f"Harvesting source: {source.name} ({source.url})")
        candidates: List[HarvestCandidate] = []

        try:
            html = await self.client.get_text(source.url)
            if not html:
                logger.warning(f"Empty HTML received for source: {source.name}")
                return []

            soup = BeautifulSoup(html, "html.parser")
            links = soup.find_all("a", href=re.compile(r"\.pdf|download|paper|syllabus|notice|GR", re.I))

            seen_urls = set()
            for a_tag in links[:30]:
                href = a_tag.get("href")
                if not href:
                    continue

                full_url = urljoin(source.url, href)
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                title = a_tag.get_text(strip=True)
                if not title or len(title) < 5:
                    title = f"{source.default_subject} - Official Document"

                # Extract year if present
                year_match = re.search(r"\b(201[5-9]|202[0-9])\b", title)
                year = int(year_match.group(1)) if year_match else 2024

                # Determine material type
                t_lower = title.lower()
                if "pyq" in t_lower or "question paper" in t_lower or "प्रश्नपत्रिका" in t_lower:
                    mat_type = MaterialType.PYQ
                elif "syllabus" in t_lower or "अभ्यासक्रम" in t_lower:
                    mat_type = MaterialType.SYLLABUS
                elif "gr" in t_lower or "शासन निर्णय" in t_lower:
                    mat_type = MaterialType.GR
                else:
                    mat_type = source.default_material_type

                candidates.append(
                    HarvestCandidate(
                        source_id=source.source_id,
                        source_name=source.name,
                        title=title[:400],
                        url=full_url,
                        exam_category=source.exam_category,
                        subject=source.default_subject,
                        material_type=mat_type,
                        year=year,
                        language=source.language,
                    )
                )

        except Exception as e:
            logger.error(f"Error harvesting source {source.name}: {e}")

        logger.info(f"Source '{source.name}' yielded {len(candidates)} candidate documents.")
        return candidates

    async def harvest_all_sources(self) -> List[HarvestCandidate]:
        """Harvest across all registered educational sources."""
        all_candidates: List[HarvestCandidate] = []
        sources = self.registry.get_all_sources(enabled_only=True)

        for s in sources:
            source_candidates = await self.harvest_source(s)
            all_candidates.extend(source_candidates)

        logger.info(f"Total harvest sweep completed: Found {len(all_candidates)} candidates across {len(sources)} sources.")
        return all_candidates
