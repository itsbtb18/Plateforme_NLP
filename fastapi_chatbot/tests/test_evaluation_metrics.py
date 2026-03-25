"""Unit tests for evaluation metrics — Precision@k, Recall@k, MRR.

Tests use synthetic mini datasets to verify expected values.
BERTScore wrapper is tested separately (optional, requires model).
"""
import sys
import os

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evaluation.metrics import (
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    mean_reciprocal_rank,
    compute_retrieval_report,
)


# ── Precision@k ──────────────────────────────────────────────────────


def test_precision_at_k_perfect():
    """All retrieved docs are relevant."""
    retrieved = ["d1", "d2", "d3", "d4", "d5"]
    relevant = {"d1", "d2", "d3", "d4", "d5"}
    assert precision_at_k(retrieved, relevant, 5) == 1.0


def test_precision_at_k_partial():
    """4 of 5 retrieved docs are relevant → P@5 = 0.8."""
    retrieved = ["d1", "d2", "d3", "d4", "d_wrong"]
    relevant = {"d1", "d2", "d3", "d4", "d5"}
    assert precision_at_k(retrieved, relevant, 5) == 0.8


def test_precision_at_k_none():
    """No retrieved docs are relevant → P@5 = 0.0."""
    retrieved = ["x1", "x2", "x3", "x4", "x5"]
    relevant = {"d1", "d2"}
    assert precision_at_k(retrieved, relevant, 5) == 0.0


def test_precision_at_k_smaller_k():
    """k < len(retrieved) → only use top-k."""
    retrieved = ["d1", "d2", "x1", "x2", "x3"]
    relevant = {"d1", "d2"}
    assert precision_at_k(retrieved, relevant, 2) == 1.0
    assert precision_at_k(retrieved, relevant, 5) == 0.4


def test_precision_at_k_zero_k():
    assert precision_at_k(["d1"], {"d1"}, 0) == 0.0


def test_precision_at_k_empty_retrieved():
    assert precision_at_k([], {"d1"}, 5) == 0.0


# ── Recall@k ─────────────────────────────────────────────────────────


def test_recall_at_k_perfect():
    retrieved = ["d1", "d2", "d3"]
    relevant = {"d1", "d2", "d3"}
    assert recall_at_k(retrieved, relevant, 5) == 1.0


def test_recall_at_k_partial():
    """1 of 3 relevant found → R@5 = 0.333..."""
    retrieved = ["d1", "x1", "x2", "x3", "x4"]
    relevant = {"d1", "d2", "d3"}
    result = recall_at_k(retrieved, relevant, 5)
    assert abs(result - 1 / 3) < 1e-6


def test_recall_at_k_empty_relevant():
    assert recall_at_k(["d1"], set(), 5) == 0.0


def test_recall_at_k_zero_k():
    assert recall_at_k(["d1"], {"d1"}, 0) == 0.0


# ── Reciprocal Rank ──────────────────────────────────────────────────


def test_reciprocal_rank_first():
    """First doc is relevant → RR = 1.0."""
    assert reciprocal_rank(["d1", "x1", "x2"], {"d1"}) == 1.0


def test_reciprocal_rank_second():
    """Second doc is relevant → RR = 0.5."""
    assert reciprocal_rank(["x1", "d1", "x2"], {"d1"}) == 0.5


def test_reciprocal_rank_third():
    """Third doc is relevant → RR ≈ 0.333."""
    result = reciprocal_rank(["x1", "x2", "d1"], {"d1"})
    assert abs(result - 1 / 3) < 1e-6


def test_reciprocal_rank_none_found():
    assert reciprocal_rank(["x1", "x2", "x3"], {"d1"}) == 0.0


# ── Mean Reciprocal Rank ─────────────────────────────────────────────


def test_mrr_perfect():
    """All queries have relevant doc at rank 1."""
    queries = [
        (["d1", "x1"], {"d1"}),
        (["d2", "x1"], {"d2"}),
    ]
    assert mean_reciprocal_rank(queries) == 1.0


def test_mrr_mixed():
    """RR values: 1.0, 0.5 → MRR = 0.75."""
    queries = [
        (["d1", "x1"], {"d1"}),       # RR = 1.0
        (["x1", "d2", "x2"], {"d2"}),  # RR = 0.5
    ]
    assert mean_reciprocal_rank(queries) == 0.75


def test_mrr_empty():
    assert mean_reciprocal_rank([]) == 0.0


# ── Aggregate report ─────────────────────────────────────────────────


def test_compute_retrieval_report():
    queries_data = [
        {
            "query": "test query 1",
            "retrieved_ids": ["d1", "d2", "x1"],
            "relevant_ids": ["d1", "d2"],
        },
        {
            "query": "test query 2",
            "retrieved_ids": ["x1", "d3", "x2"],
            "relevant_ids": ["d3"],
        },
    ]
    report = compute_retrieval_report(queries_data, k=3)

    assert "aggregate" in report
    assert "per_query" in report
    assert "failure_cases" in report
    assert report["aggregate"]["k"] == 3
    assert report["aggregate"]["num_queries"] == 2
    assert 0.0 <= report["aggregate"]["precision_at_k"] <= 1.0
    assert 0.0 <= report["aggregate"]["recall_at_k"] <= 1.0
    assert 0.0 <= report["aggregate"]["mrr"] <= 1.0


def test_report_identifies_failures():
    """Query with 0 recall should appear in failure_cases."""
    queries_data = [
        {
            "query": "found nothing",
            "retrieved_ids": ["x1", "x2"],
            "relevant_ids": ["d1", "d2"],
        },
    ]
    report = compute_retrieval_report(queries_data, k=5)
    assert len(report["failure_cases"]) == 1
    assert report["failure_cases"][0]["query"] == "found nothing"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
