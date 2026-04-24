"""
Deduplication and reranking utilities for retrieval results.
"""
from typing import Dict, List
import hashlib
import logging

from app.services.documents.embeddings import get_embedding_service

logger = logging.getLogger(__name__)

# Minimum content length (chars) below which a chunk is too short to be useful
_MIN_CONTENT_LEN = 20

# Jaccard similarity threshold for near-duplicate detection
_DEDUP_JACCARD_THRESHOLD = 0.85


def deduplicate(docs: List[Dict]) -> List[Dict]:
    """Remove near-duplicate documents based on content Jaccard similarity."""
    if not docs:
        return docs

    kept: List[Dict] = []
    seen_hashes: set = set()

    for doc in docs:
        content = (doc.get("content") or "").strip()
        if len(content) < _MIN_CONTENT_LEN:
            continue

        # Exact-duplicate check via hash
        h = hashlib.md5(content.encode("utf-8")).hexdigest()
        if h in seen_hashes:
            continue

        # Near-duplicate check via word-set Jaccard
        words = set(content.lower().split())
        is_near_dup = False
        for prev in kept:
            prev_words = set((prev.get("content") or "").lower().split())
            if not words or not prev_words:
                continue
            intersection = len(words & prev_words)
            union = len(words | prev_words)
            if union and intersection / union >= _DEDUP_JACCARD_THRESHOLD:
                is_near_dup = True
                break

        if not is_near_dup:
            seen_hashes.add(h)
            kept.append(doc)

    return kept


def rerank(query: str, docs: List[Dict], top_n: int = 5) -> List[Dict]:
    """
    Re-score documents by computing fresh cosine similarity between
    the query embedding and a re-encoded version of each doc's content.

    Falls back to the original ranking on any error.
    """
    if len(docs) <= top_n:
        return docs

    try:
        import numpy as np

        embedding_svc = get_embedding_service()
        query_emb = embedding_svc.encode_single(query)
        texts = [(d.get("content") or "")[:500] for d in docs[:top_n * 2]]
        doc_embs = embedding_svc.encode(texts).tolist()

        q = np.array(query_emb)

        for doc, d_emb in zip(docs[:len(doc_embs)], doc_embs):
            d = np.array(d_emb)
            cos = float(
                np.dot(q, d) / (np.linalg.norm(q) * np.linalg.norm(d) + 1e-9)
            )
            doc["rerank_score"] = cos

        reranked = sorted(
            docs[:len(doc_embs)],
            key=lambda x: x.get("rerank_score", 0),
            reverse=True,
        )
        for r in reranked:
            r.pop("rerank_score", None)
        return reranked[:top_n]

    except Exception as e:
        logger.warning("Reranking failed, using original order: %s", e)
        return docs[:top_n]
