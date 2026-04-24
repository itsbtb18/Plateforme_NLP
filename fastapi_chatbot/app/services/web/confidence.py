"""Retrieval confidence scoring and conservative Exa fallback gating.

Computes a composite confidence score from retrieval signals:
    confidence = 0.4 * similarity_score + 0.3 * reranker_score + 0.3 * document_agreement

Routing thresholds:
    > 0.75     -> normal RAG answer
    0.50-0.75 -> LLM fallback (no web)
    < 0.50    -> candidate for Exa fallback (eligible intents only)

Exa fallback is intentionally conservative to avoid unnecessary paid web calls.
"""

import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

# Thresholds
CONFIDENCE_HIGH = 0.75    # Normal RAG answer
CONFIDENCE_MEDIUM = 0.50  # LLM fallback, no web search
CONFIDENCE_MEDIUM_CONCEPTUAL = 0.52
CONFIDENCE_MEDIUM_GENERAL = 0.55  # Higher bar for general_knowledge Exa triggers

# Extra guardrails to avoid triggering Exa when local retrieval is still usable.
EXA_MIN_TOP_SIMILARITY = 0.45
EXA_MIN_SECOND_SIMILARITY = 0.40
EXA_MIN_QUERY_DOC_OVERLAP = 0.15
EXA_SIMILARITY_STRONG_LOCAL = 0.62

# When Exa fallback is triggered, decide whether to keep only Exa docs
# or merge with local vector docs.
WEB_ONLY_TOP_SIM_MAX = 0.56
WEB_ONLY_OVERLAP_MAX = 0.10

STOPWORDS = {
    "about", "after", "all", "also", "and", "any", "are", "can", "could",
    "does", "for", "from", "get", "how", "into", "its", "like", "merge",
    "more", "need", "not", "our", "out", "should", "that", "the", "their",
    "them", "then", "there", "they", "this", "use", "using", "what", "when",
    "where", "which", "who", "why", "with", "you", "your", "api", "key",
    "both", "latest", "details", "guide", "help", "please",
}


def _tokenize(text: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[a-zA-Z0-9]{3,}", (text or "").lower())
        if t not in STOPWORDS
    }


def _query_doc_overlap_ratio(query: str, docs: List[Dict], *, top_k: int = 2) -> float:
    """Return query token overlap ratio against top retrieved docs.

    ratio = |query_tokens ∩ doc_tokens| / |query_tokens|
    """
    query_tokens = _tokenize(query)
    if not query_tokens or not docs:
        return 0.0

    doc_tokens: set[str] = set()
    for d in docs[:top_k]:
        parts = [
            str(d.get("title", "")),
            str(d.get("snippet", "")),
            str(d.get("chunk", "")),
            str(d.get("content", "")),
            str(d.get("text", "")),
        ]
        doc_tokens.update(_tokenize(" ".join(parts)))

    if not doc_tokens:
        return 0.0

    return len(query_tokens.intersection(doc_tokens)) / len(query_tokens)


def _extract_requested_article_number(query: str) -> str | None:
    """Extract an explicitly requested legal article number, if present."""
    if not query:
        return None
    m = re.search(r"\b(?:article|art\.?|المادة|مادة)\s*(\d{1,4})\b", query.lower())
    if m:
        return m.group(1)
    return None


def _docs_contain_article_number(docs: List[Dict], article_no: str, *, top_k: int = 3) -> bool:
    """Return True if the top docs mention the requested article number."""
    if not docs or not article_no:
        return False
    pattern = re.compile(
        rf"\b(?:article|art\.?|المادة|مادة)\s*{re.escape(article_no)}\b|\b{re.escape(article_no)}\b",
        re.IGNORECASE,
    )
    for d in docs[:top_k]:
        blob = " ".join(
            [
                str(d.get("title", "")),
                str(d.get("snippet", "")),
                str(d.get("chunk", "")),
                str(d.get("content", "")),
                str(d.get("text", "")),
            ]
        )
        if pattern.search(blob):
            return True
    return False


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
    retrieved_docs: List[Dict] | None = None,
    question: str | None = None,
    mode: str | None = None,
) -> bool:
    """Determine whether Exa fallback should be triggered.

    Exa is ONLY triggered when:
      - confidence < CONFIDENCE_MEDIUM (0.50)
      - intent is legal_query or conceptual_question
    - local retrieval quality is weak (or no docs)
    - local docs do not lexically match the query enough
    """
    eligible_intents = {"legal_query", "conceptual_question", "general_knowledge"}

    if intent not in eligible_intents:
        return False

    if intent == "general_knowledge":
        threshold = CONFIDENCE_MEDIUM_GENERAL
    elif intent == "conceptual_question":
        threshold = CONFIDENCE_MEDIUM_CONCEPTUAL
    else:
        threshold = CONFIDENCE_MEDIUM

    # Mode-aware boost: if the user explicitly selected a domain-expert mode,
    # we are more willing to search the web to ensure they get a "full" answer.
    if mode in ("legal", "nlp_ai"):
        logger.info("Boosting Exa fallback sensitivity for mode: %s", mode)
        threshold += 0.10  # Search web even with borderline confidence

    # Legal precision override: if the user asks for a specific article number,
    # and local docs don't contain that article while overlap is weak, allow Exa
    # fallback even when confidence is borderline/high from unrelated chunks.
    if intent == "legal_query" and question and retrieved_docs:
        requested_article = _extract_requested_article_number(question)
        if requested_article:
            overlap = _query_doc_overlap_ratio(question, retrieved_docs)
            contains_article = _docs_contain_article_number(
                retrieved_docs,
                requested_article,
            )
            if not contains_article and overlap < EXA_MIN_QUERY_DOC_OVERLAP:
                logger.info(
                    "Exa fallback forced for legal article lookup: article=%s overlap=%.3f",
                    requested_article,
                    overlap,
                )
                return True

    if confidence >= threshold:
        return False

    # If nothing local was retrieved, allow Exa fallback.
    if not retrieved_docs:
        return True

    sims = sorted((d.get("similarity", 0.0) for d in retrieved_docs), reverse=True)
    top_sim = sims[0] if sims else 0.0
    second_sim = sims[1] if len(sims) > 1 else 0.0

    if question:
        overlap = _query_doc_overlap_ratio(question, retrieved_docs)
        # For out-of-corpus queries, allow Exa even with borderline similarity,
        # unless local top similarity is very strong.
        if overlap < EXA_MIN_QUERY_DOC_OVERLAP and top_sim < EXA_SIMILARITY_STRONG_LOCAL:
            logger.info(
                "Exa fallback forced by low query-doc overlap: overlap=%.3f top_sim=%.3f",
                overlap,
                top_sim,
            )
            return True
        if overlap >= EXA_MIN_QUERY_DOC_OVERLAP:
            logger.info(
                "Exa fallback blocked by query-doc overlap: overlap=%.3f",
                overlap,
            )
            return False

    # Avoid web fallback when local docs look reasonably relevant.
    if top_sim >= EXA_MIN_TOP_SIMILARITY:
        return False
    if second_sim >= EXA_MIN_SECOND_SIMILARITY:
        return False

    return True


def should_use_web_only_context(
    retrieved_docs: List[Dict] | None,
    question: str | None,
    intent: str,
) -> bool:
    """Return True when Exa docs should replace local docs entirely.

    This is used after Exa fallback has already triggered. We prefer web-only
    when local vector hits are weak/lexically unrelated so irrelevant corpus
    chunks (e.g., unrelated NLP papers) don't pollute the final answer.
    """
    if intent not in {"conceptual_question", "legal_query"}:
        return False

    if not retrieved_docs:
        return True

    sims = sorted((d.get("similarity", 0.0) for d in retrieved_docs), reverse=True)
    top_sim = sims[0] if sims else 0.0
    overlap = _query_doc_overlap_ratio(question or "", retrieved_docs)

    return top_sim <= WEB_ONLY_TOP_SIM_MAX and overlap <= WEB_ONLY_OVERLAP_MAX
