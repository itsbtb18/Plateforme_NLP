"""
Exa search client — RAG fallback retrieval layer.

Triggered ONLY when:
  - intent is legal_query OR conceptual_question
  - retrieval confidence < 0.50
  - NOT a platform/user/document mode

Results are normalized into the internal doc format and fed into the
existing RRF + rerank pipeline — they never bypass the RAG stack.
"""

import hashlib
import logging
import time
from typing import Dict, List, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _normalize_exa_result(result, rank: int) -> Dict:
    """Convert an Exa result object into the internal doc format."""
    return {
        "title": getattr(result, "title", "") or "",
        "content": getattr(result, "text", "") or "",
        "source": "web_exa",
        "url": getattr(result, "url", "") or "",
        "similarity": max(0.35, 0.55 - rank * 0.04),  # Synthetic score for ranking (lowered Phase 6)
        "metadata": {
            "source_type": "web",
            "provider": "exa",
            "published_date": getattr(result, "published_date", None),
        },
    }


async def search_exa(
    query: str,
    *,
    intent: str = "conceptual_question",
    language: str = "en",
    num_results: int = 5,
) -> List[Dict]:
    """Search via Exa API and return normalized docs.

    Args:
        query: search query text
        intent: classified intent (affects search type)
        language: detected language code
        num_results: max results to return

    Returns:
        List of normalized doc dicts ready for RRF fusion.
    """
    if not settings.EXA_ENABLED or not settings.EXA_API_KEY:
        logger.debug("Exa search skipped: disabled or no API key")
        return []

    # Import lazily to avoid import errors when exa-py isn't installed
    try:
        from exa_py import Exa
    except ImportError:
        logger.warning("exa-py package not installed — Exa search unavailable")
        return []

    search_type = "deep" if intent == "legal_query" else "auto"

    try:
        start = time.monotonic()
        exa = Exa(api_key=settings.EXA_API_KEY)

        results = exa.search_and_contents(
            query,
            type=search_type,
            num_results=num_results,
            text={"max_characters": 8000},
        )

        elapsed = time.monotonic() - start
        docs = [
            _normalize_exa_result(r, i)
            for i, r in enumerate(results.results)
        ]

        logger.info(
            "Exa search complete: query='%s' type=%s results=%d latency=%.2fs",
            query[:60], search_type, len(docs), elapsed,
        )
        return docs

    except Exception as e:
        logger.error("Exa search failed: %s", e)
        return []
