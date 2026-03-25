"""
Evaluation metrics — Precision@k, Recall@k, MRR, BERTScore.

These match the formulas from the project report (Section 15):
- Precision@k = (relevant docs in top-k) / k
- Recall@k    = (relevant docs in top-k) / total relevant docs
- MRR         = 1/Q × Σ 1/rank_i  (first relevant rank per query)
- BERTScore   = semantic similarity between reference and candidate
"""

import logging
from typing import List, Set, Tuple, Dict, Optional

logger = logging.getLogger(__name__)


# ── Retrieval metrics ─────────────────────────────────────────────────


def precision_at_k(
    retrieved: List[str],
    relevant: Set[str],
    k: int,
) -> float:
    """P@k = |{relevant docs in top-k}| / k

    Args:
        retrieved: Ordered list of document IDs (best first).
        relevant:  Set of ground-truth relevant document IDs.
        k:         Cut-off rank.

    Returns:
        Precision value in [0.0, 1.0].
    """
    if k <= 0:
        return 0.0
    top_k = list(dict.fromkeys(retrieved[:k]))
    relevant_in_top_k = len(set(top_k) & relevant)
    return relevant_in_top_k / k


def recall_at_k(
    retrieved: List[str],
    relevant: Set[str],
    k: int,
) -> float:
    """R@k = |{relevant docs in top-k}| / |relevant|

    Args:
        retrieved: Ordered list of document IDs.
        relevant:  Set of ground-truth relevant document IDs.
        k:         Cut-off rank.

    Returns:
        Recall value in [0.0, 1.0].
    """
    if not relevant or k <= 0:
        return 0.0
    top_k = list(dict.fromkeys(retrieved[:k]))
    relevant_in_top_k = len(set(top_k) & relevant)
    return relevant_in_top_k / len(relevant)


def reciprocal_rank(
    retrieved: List[str],
    relevant: Set[str],
) -> float:
    """1 / rank of first relevant document. 0.0 if none found."""
    for i, doc_id in enumerate(retrieved, 1):
        if doc_id in relevant:
            return 1.0 / i
    return 0.0


def mean_reciprocal_rank(
    queries_results: List[Tuple[List[str], Set[str]]],
) -> float:
    """MRR = (1/Q) × Σ 1/rank_i

    Args:
        queries_results: List of (retrieved_ids, relevant_ids) per query.

    Returns:
        MRR value in [0.0, 1.0].
    """
    if not queries_results:
        return 0.0
    total_rr = sum(
        reciprocal_rank(retrieved, relevant)
        for retrieved, relevant in queries_results
    )
    return total_rr / len(queries_results)


# ── Generation metrics ────────────────────────────────────────────────


def compute_bert_score(
    references: List[str],
    candidates: List[str],
    lang: str = "fr",
    model_type: Optional[str] = None,
) -> Dict[str, float]:
    """BERTScore between reference answers and model answers.

    Formula (simplified): BERTScore = (1/n) × Σ_i max_j cos(r_i, g_j)

    Args:
        references: Ground-truth answers.
        candidates: Model-generated answers.
        lang:       Language code (affects default model selection).
        model_type: Override BERT model (default: auto-select by lang).

    Returns:
        Dict with 'precision', 'recall', 'f1' (averaged over all pairs).
    """
    try:
        from bert_score import score as bert_score_fn

        P, R, F1 = bert_score_fn(
            candidates,
            references,
            lang=lang,
            model_type=model_type,
            verbose=False,
        )
        return {
            "precision": float(P.mean()),
            "recall": float(R.mean()),
            "f1": float(F1.mean()),
        }
    except ImportError:
        logger.warning(
            "bert_score package not installed. "
            "Install with: pip install bert_score"
        )
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    except Exception as e:
        logger.error("BERTScore computation failed: %s", e)
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}


# ── Aggregate report builder ─────────────────────────────────────────


def compute_retrieval_report(
    queries_data: List[Dict],
    k: int = 5,
) -> Dict:
    """Compute aggregate retrieval metrics from evaluation data.

    Args:
        queries_data: List of dicts with keys:
            - query (str)
            - retrieved_ids (List[str])
            - relevant_ids (List[str])
        k: Cut-off for P@k and R@k.

    Returns:
        Dict with aggregate and per-query metrics.
    """
    per_query = []
    all_results = []

    for item in queries_data:
        retrieved = item["retrieved_ids"]
        relevant = set(item["relevant_ids"])
        p = precision_at_k(retrieved, relevant, k)
        r = recall_at_k(retrieved, relevant, k)
        rr = reciprocal_rank(retrieved, relevant)
        per_query.append({
            "query": item["query"],
            "precision_at_k": round(p, 4),
            "recall_at_k": round(r, 4),
            "reciprocal_rank": round(rr, 4),
        })
        all_results.append((retrieved, relevant))

    mrr = mean_reciprocal_rank(all_results)

    # Identify failure cases (low recall)
    failures = [q for q in per_query if q["recall_at_k"] < 0.5]

    n = len(per_query)
    avg_p = sum(q["precision_at_k"] for q in per_query) / n if n else 0.0
    avg_r = sum(q["recall_at_k"] for q in per_query) / n if n else 0.0

    return {
        "aggregate": {
            "precision_at_k": round(avg_p, 4),
            "recall_at_k": round(avg_r, 4),
            "mrr": round(mrr, 4),
            "k": k,
            "num_queries": n,
        },
        "per_query": per_query,
        "failure_cases": failures,
    }
