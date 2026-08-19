"""Cloud-Native Hybrid Search Engine (Gemini AI Embeddings + RapidFuzz Lexical)."""

from functools import lru_cache
import logging
import math
import os
from typing import Dict, List, Optional, Sequence, Tuple
import httpx
from rapidfuzz import fuzz
from config.settings import get_settings
from database.models import StudyMaterial, ExamCategory, MaterialType

logger = logging.getLogger(__name__)
settings = get_settings()

# In-memory vector embeddings cache: (text_hash -> 768-dim list of floats)
_EMBEDDING_CACHE: Dict[str, List[float]] = {}


def compute_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


async def get_gemini_embedding(text: str, api_key: Optional[str] = None) -> Optional[List[float]]:
    """Fetch 768-dimensional text embedding from Google Gemini API (text-embedding-004)."""
    key = api_key or os.getenv("GEMINI_API_KEY") or settings.gemini_api_key
    if not key:
        return None

    text_clean = text.strip()[:1000]
    if not text_clean:
        return None

    if text_clean in _EMBEDDING_CACHE:
        return _EMBEDDING_CACHE[text_clean]

    url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={key}"
    payload = {
        "model": "models/text-embedding-004",
        "content": {
            "parts": [{"text": text_clean}]
        }
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                values = data.get("embedding", {}).get("values", [])
                if values:
                    _EMBEDDING_CACHE[text_clean] = values
                    return values
            else:
                logger.debug(f"Gemini embedding API returned status {resp.status_code}")
    except Exception as e:
        logger.debug(f"Gemini embedding request failed: {e}")

    return None


async def rank_hybrid_materials(
    query: str,
    candidates: Sequence[StudyMaterial],
    expanded_terms: List[str],
    api_key: Optional[str] = None,
) -> List[StudyMaterial]:
    """Rank candidate materials using Reciprocal Rank Fusion (RapidFuzz + Gemini AI)."""
    if not candidates:
        return []

    # --------------------------------------------------------------------------
    # 1. Lexical Scoring (RapidFuzz)
    # --------------------------------------------------------------------------
    lexical_scored: List[Tuple[float, StudyMaterial]] = []
    query_clean = query.strip()

    for item in candidates:
        target_text = f"{item.title} {item.subject} {item.exam_category.value}"
        score_direct = fuzz.token_set_ratio(query_clean, target_text)
        score_partial = fuzz.partial_ratio(query_clean, target_text)

        max_syn_score = 0.0
        for syn in expanded_terms[:6]:
            s_score = fuzz.token_set_ratio(syn, target_text)
            if s_score > max_syn_score:
                max_syn_score = s_score

        final_lex_score = max(score_direct, score_partial, max_syn_score)
        lexical_scored.append((final_lex_score, item))

    # Sort descending by lexical score
    lexical_scored.sort(key=lambda x: x[0], reverse=True)
    lexical_ranks = {item.id: rank for rank, (_, item) in enumerate(lexical_scored)}

    # --------------------------------------------------------------------------
    # 2. Semantic Scoring (Gemini Embeddings if API Key is configured)
    # --------------------------------------------------------------------------
    query_vec = await get_gemini_embedding(query_clean, api_key=api_key)
    semantic_ranks: Dict[int, int] = {}

    if query_vec:
        sem_scored: List[Tuple[float, StudyMaterial]] = []
        for item in candidates:
            doc_text = f"{item.title} {item.subject} {item.exam_category.value}"
            doc_vec = await get_gemini_embedding(doc_text, api_key=api_key)
            if doc_vec:
                sim = compute_cosine_similarity(query_vec, doc_vec)
                sem_scored.append((sim, item))
            else:
                sem_scored.append((0.0, item))

        sem_scored.sort(key=lambda x: x[0], reverse=True)
        semantic_ranks = {item.id: rank for rank, (_, item) in enumerate(sem_scored)}

    # --------------------------------------------------------------------------
    # 3. Reciprocal Rank Fusion (RRF)
    # --------------------------------------------------------------------------
    k = 60  # Standard RRF smoothing constant
    rrf_scores: List[Tuple[float, StudyMaterial]] = []

    for item in candidates:
        lex_rank = lexical_ranks.get(item.id, 999)
        rrf = 1.0 / (k + lex_rank)

        if semantic_ranks:
            sem_rank = semantic_ranks.get(item.id, 999)
            rrf += 1.0 / (k + sem_rank)

        rrf_scores.append((rrf, item))

    rrf_scores.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in rrf_scores]
