"""
Hybrid search — weighted merge across all knowledge collections,
with deduplication and reranking.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional, Tuple
import logging

from app.config import get_settings
from app.services.retrieval.search import (
    search_platform_docs,
    search_nlp_knowledge,
    search_resources,
    search_legal_documents,
)
from app.services.retrieval.reranker import deduplicate, rerank

logger = logging.getLogger(__name__)
settings = get_settings()


async def hybrid_search(
    query: str, db: AsyncSession,
    user_country: Optional[str] = None,
    user_city: Optional[str] = None,
    include_legal: bool = True,
    language: Optional[str] = None,
) -> Tuple[List[Dict], str]:
    """
    Weighted hybrid search across every source.
    Returns (combined_results, primary_source).

    Phase 5 improvements:
      - Language-aware metadata filtering where applicable
      - Content-based deduplication
      - top_k control per collection
    """
    try:
        platform_docs = await search_platform_docs(query, db, top_k=4)
        nlp_knowledge = await search_nlp_knowledge(
            query, db, top_k=4, language=language,
        )
        resources_results = await search_resources(
            query, db, top_k=4,
            user_country=user_country, user_city=user_city,
        )

        weighted: List[Dict] = []

        for d in platform_docs:
            d["weighted_score"] = d["similarity"] * 1.1
            weighted.append(d)
        for d in nlp_knowledge:
            d["weighted_score"] = d["similarity"] * 1.0
            weighted.append(d)
        for d in resources_results:
            boost = 1.0
            if user_country and d.get("country") == user_country:
                boost += 0.05
            if user_city and d.get("city") == user_city:
                boost += 0.05
            d["weighted_score"] = d["similarity"] * boost
            weighted.append(d)

        # Legal
        if include_legal:
            legal = await search_legal_documents(
                query, db, top_k=3, language=language,
            )
            for d in legal:
                d["weighted_score"] = d["similarity"] * 1.05
                weighted.append(d)

        if not weighted:
            logger.info("No results for: %s...", query[:50])
            return [], "none"

        weighted.sort(key=lambda x: x["weighted_score"], reverse=True)
        primary_source = weighted[0]["source"]

        # Qdrant already applies score_threshold server-side — no need
        # to re-filter here (was causing over-aggressive result pruning).

        # Deduplicate near-identical content
        deduped = deduplicate(weighted)

        # Reranking (re-score top results against query)
        reranked = rerank(query, deduped, top_n=settings.TOP_K_RESULTS)

        for r in reranked:
            r.pop("weighted_score", None)

        logger.info(
            "Hybrid search: %d raw → %d deduped → %d final, primary=%s",
            len(weighted), len(deduped), len(reranked), primary_source,
        )
        return reranked, primary_source

    except Exception as e:
        logger.error("Hybrid search error: %s", e, exc_info=True)
        return [], "none"
