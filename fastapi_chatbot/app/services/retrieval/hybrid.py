"""
Hybrid search — dense (Qdrant) + sparse (BM25) with RRF fusion.

Phase 4 rewrite: replaces the old weighted-cosine approach with
Reciprocal Rank Fusion (RRF), which is parameter-free beyond the
constant k=60 (from the original RRF paper, Cormack et al. 2009).

Pipeline:
  1. Run dense search (Qdrant cosine) across requested collections
  2. Run sparse search (BM25) across same collections
  3. Fuse results using RRF
  4. Deduplicate near-identical content
  5. Rerank top candidates

The old source-specific weight multipliers (×1.05, ×1.1) are removed.
"""

import logging
from typing import Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.retrieval.search import (
    search_platform_docs,
    search_nlp_knowledge,
    search_resources,
    search_legal_documents,
)
from app.services.retrieval.bm25 import search_bm25
from app.services.retrieval.reranker import deduplicate, rerank

logger = logging.getLogger(__name__)

# RRF constant — from the original paper.  k=60 is standard.
RRF_K = 60


def _rrf_fuse(
    dense_results: List[Dict],
    sparse_results: List[Dict],
    *,
    k: int = RRF_K,
) -> List[Dict]:
    """Fuse dense and sparse results using Reciprocal Rank Fusion.

    For each document d:
        RRF_score(d) = Σ 1 / (k + rank_i(d))

    where rank_i is the 1-based rank in list i.

    Documents are identified by their "content" field (first 200 chars)
    to handle cases where the same content appears with different metadata.
    """
    # Build score map: content_key → {doc, score}
    fused: Dict[str, Dict] = {}

    def _key(doc: Dict) -> str:
        """Create a stable key for dedup during fusion."""
        content = (doc.get("content") or "")[:200]
        source = doc.get("source", "")
        return f"{source}::{content}"

    # Score from dense results
    for rank, doc in enumerate(dense_results, start=1):
        key = _key(doc)
        if key not in fused:
            fused[key] = {"doc": dict(doc), "score": 0.0}
        fused[key]["score"] += 1.0 / (k + rank)

    # Score from sparse results
    for rank, doc in enumerate(sparse_results, start=1):
        key = _key(doc)
        if key not in fused:
            fused[key] = {"doc": dict(doc), "score": 0.0}
        fused[key]["score"] += 1.0 / (k + rank)

    # Sort by fused score descending
    ranked = sorted(fused.values(), key=lambda x: x["score"], reverse=True)

    # Return docs with RRF score attached
    results = []
    for entry in ranked:
        doc = entry["doc"]
        doc["rrf_score"] = entry["score"]
        results.append(doc)

    return results


async def hybrid_search(
    query: str,
    db: AsyncSession,
    *,
    language: str = "en",
    top_k: int = 5,
    include_legal: bool = False,
    jurisdiction: Optional[str] = None,
    user_country: Optional[str] = None,
    user_city: Optional[str] = None,
) -> Tuple[List[Dict], str]:
    """Cross-collection hybrid search: dense + sparse → RRF → dedup → rerank.

    Args:
        query: user query text
        db: async database session (required by per-collection search funcs)
        language: detected language (ar/fr/en)
        top_k: final number of results to return
        include_legal: whether to include legal_documents collection
        jurisdiction: optional country code for legal filtering
        user_country: optional country for geo-boosting resources
        user_city: optional city for geo-boosting resources

    Returns:
        Tuple of (results_list, primary_source_name)
    """
    # ── 1. Dense retrieval (Qdrant cosine) ────────────────────────────
    dense_results: List[Dict] = []
    primary_source = "qdrant"

    try:
        platform = await search_platform_docs(query, db)
        dense_results.extend(platform)
    except Exception as e:
        logger.warning("Dense search (platform_docs) failed: %s", e)

    try:
        nlp = await search_nlp_knowledge(query, db, language=language)
        dense_results.extend(nlp)
    except Exception as e:
        logger.warning("Dense search (nlp_knowledge) failed: %s", e)

    try:
        resources = await search_resources(
            query, db,
            user_country=user_country,
            user_city=user_city,
        )
        dense_results.extend(resources)
    except Exception as e:
        logger.warning("Dense search (resources) failed: %s", e)

    if include_legal:
        try:
            legal = await search_legal_documents(
                query, db,
                language=language,
                jurisdiction=jurisdiction,
            )
            dense_results.extend(legal)
        except Exception as e:
            logger.warning("Dense search (legal_documents) failed: %s", e)

    # ── 2. Sparse retrieval (BM25) ────────────────────────────────────
    sparse_results: List[Dict] = []

    for collection in ["platform_docs", "nlp_knowledge", "resources"]:
        try:
            bm25_hits = search_bm25(query, collection, top_k=top_k * 2)
            sparse_results.extend(bm25_hits)
        except Exception as e:
            logger.debug("BM25 search (%s) skipped: %s", collection, e)

    if include_legal:
        try:
            bm25_legal = search_bm25(query, "legal_documents", top_k=top_k * 2)
            sparse_results.extend(bm25_legal)
        except Exception as e:
            logger.debug("BM25 search (legal_documents) skipped: %s", e)

    # ── 3. Fuse with RRF ─────────────────────────────────────────────
    if dense_results or sparse_results:
        fused = _rrf_fuse(dense_results, sparse_results)
        logger.info(
            "RRF fusion: %d dense + %d sparse → %d fused",
            len(dense_results), len(sparse_results), len(fused),
        )
    else:
        fused = []

    # ── 4. Deduplicate ────────────────────────────────────────────────
    deduped = deduplicate(fused)

    # ── 5. Rerank top candidates ──────────────────────────────────────
    final = rerank(query, deduped, top_n=top_k)

    logger.info(
        "Hybrid search complete: %d results (dense=%d sparse=%d fused=%d dedup=%d)",
        len(final), len(dense_results), len(sparse_results),
        len(fused), len(deduped),
    )

    return final, primary_source
