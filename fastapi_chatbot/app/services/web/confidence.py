"""
Retrieval confidence scoring.

Computes a composite confidence score from retrieval signals:
    confidence = 0.4 * similarity_score + 0.3 * reranker_score + 0.3 * document_agreement

Routing thresholds:
    > 0.75  → normal RAG answer
    0.50–0.75 → LLM fallback (no web)
    < 0.50  → Exa fallback retrieval (legal/NLP intents only)
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# Thresholds
CONFIDENCE_HIGH = 0.75    # Normal RAG answer
CONFIDENCE_MEDIUM = 0.50  # LLM fallback, no web search
# Below CONFIDENCE_MEDIUM → Exa fallback (for eligible intents)


def compute_retrieval_confidence(
    retrieved_docs: List[Dict],
    *,
    reranker_scores: List[float] | None = None,
) -> float:
    """Compute composite retrieval confidence from available signals.

    Args:
        retrieved_docs: list of retrieved doc dicts (must have "similarity" key)
        reranker_scores: optional list of reranker scores (one per doc)

    Returns:
        Confidence score in [0.0, 1.0].
    """
    if not retrieved_docs:
        return 0.0

    # ── 1. Similarity score: average of top-3 doc similarities ────────
    similarities = [d.get("similarity", 0.0) for d in retrieved_docs]
    top_sims = sorted(similarities, reverse=True)[:3]
    avg_similarity = sum(top_sims) / len(top_sims) if top_sims else 0.0

    # ── 2. Reranker score: average of available reranker scores ───────
    if reranker_scores and len(reranker_scores) > 0:
        avg_reranker = sum(reranker_scores) / len(reranker_scores)
    else:
        # Default: use similarity as reranker proxy (slightly penalized)
        avg_reranker = avg_similarity * 0.85

    # ── 3. Document agreement: how consistent are the top results? ────
    # Measured by the ratio of docs above the median similarity.
    if len(similarities) >= 2:
        median_sim = sorted(similarities)[len(similarities) // 2]
        above_median = sum(1 for s in similarities if s >= median_sim)
        agreement = above_median / len(similarities)
    else:
        agreement = avg_similarity  # Single doc → agree with itself

    # ── Composite ─────────────────────────────────────────────────────
    confidence = (
        0.4 * avg_similarity
        + 0.3 * avg_reranker
        + 0.3 * agreement
    )

    # Clamp to [0, 1]
    confidence = max(0.0, min(1.0, confidence))

    logger.debug(
        "Retrieval confidence: %.3f (sim=%.3f rerank=%.3f agreement=%.3f docs=%d)",
        confidence, avg_similarity, avg_reranker, agreement, len(retrieved_docs),
    )

    return confidence


def should_trigger_exa(
    confidence: float,
    intent: str,
) -> bool:
    """Determine whether Exa fallback should be triggered.

    Exa is ONLY triggered when:
      - confidence < CONFIDENCE_MEDIUM (0.50)
      - intent is legal_query or conceptual_question
    """
    eligible_intents = {"legal_query", "conceptual_question"}

    if intent not in eligible_intents:
        return False

    if confidence >= CONFIDENCE_MEDIUM:
        return False

    return True
