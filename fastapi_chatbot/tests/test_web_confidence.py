"""Unit tests for web search confidence scoring."""
import sys
import os

# Allow running from project root — add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.web.confidence import (
    compute_retrieval_confidence,
    should_trigger_exa,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
)


# ── compute_retrieval_confidence ──────────────────────────────────


def test_empty_docs_returns_zero():
    assert compute_retrieval_confidence([]) == 0.0


def test_high_similarity_returns_above_threshold():
    docs = [
        {"similarity": 0.92},
        {"similarity": 0.88},
        {"similarity": 0.85},
    ]
    confidence = compute_retrieval_confidence(docs)
    assert confidence > CONFIDENCE_HIGH, f"Expected > {CONFIDENCE_HIGH}, got {confidence}"


def test_low_similarity_returns_below_medium():
    docs = [
        {"similarity": 0.15},
        {"similarity": 0.12},
    ]
    confidence = compute_retrieval_confidence(docs)
    assert confidence < CONFIDENCE_MEDIUM, f"Expected < {CONFIDENCE_MEDIUM}, got {confidence}"


def test_medium_similarity_returns_between_thresholds():
    docs = [
        {"similarity": 0.60},
        {"similarity": 0.55},
        {"similarity": 0.50},
    ]
    confidence = compute_retrieval_confidence(docs)
    assert CONFIDENCE_MEDIUM <= confidence <= CONFIDENCE_HIGH, (
        f"Expected between {CONFIDENCE_MEDIUM} and {CONFIDENCE_HIGH}, got {confidence}"
    )


def test_missing_similarity_uses_default_zero():
    docs = [{"content": "some text"}, {"content": "other text"}]
    confidence = compute_retrieval_confidence(docs)
    assert confidence == 0.0


def test_single_doc_confidence():
    docs = [{"similarity": 0.80}]
    confidence = compute_retrieval_confidence(docs)
    assert confidence > 0.0


def test_reranker_scores_boost_confidence():
    docs = [{"similarity": 0.50}, {"similarity": 0.45}]
    without_reranker = compute_retrieval_confidence(docs)
    with_reranker = compute_retrieval_confidence(docs, reranker_scores=[0.90, 0.85])
    assert with_reranker > without_reranker, (
        f"Reranker should boost: {with_reranker} > {without_reranker}"
    )


def test_confidence_clamped_to_one():
    docs = [{"similarity": 1.0}, {"similarity": 1.0}, {"similarity": 1.0}]
    confidence = compute_retrieval_confidence(docs, reranker_scores=[1.0, 1.0, 1.0])
    assert confidence <= 1.0


# ── should_trigger_exa ────────────────────────────────────────────


def test_exa_triggered_for_low_conf_legal():
    assert should_trigger_exa(0.30, "legal_query") is True


def test_exa_triggered_for_low_conf_conceptual():
    assert should_trigger_exa(0.40, "conceptual_question") is True


def test_exa_not_triggered_for_high_confidence():
    assert should_trigger_exa(0.80, "legal_query") is False


def test_exa_not_triggered_for_medium_confidence():
    assert should_trigger_exa(0.55, "conceptual_question") is False


def test_exa_not_triggered_for_platform_intent():
    assert should_trigger_exa(0.10, "platform_query") is False


def test_exa_not_triggered_for_general_knowledge():
    assert should_trigger_exa(0.10, "general_knowledge") is False


def test_exa_not_triggered_for_document_intent():
    assert should_trigger_exa(0.10, "document_query") is False


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
