#!/usr/bin/env python
"""Evaluation runner for retrieval/generation metrics.

Supports:
- Scenario-based retrieval lists (baseline, reranker_top5, exa_fallback_top5)
- Optional noise filtering (e.g., Exa/web pages)
- Intent scope filtering (all/rag/memory)
- Retrieval metrics: Precision@k, Recall@k, MRR
- Optional generation metric: BERTScore
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path for standalone execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.metrics import compute_retrieval_report, compute_bert_score

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

DATASET_PATH = Path(__file__).parent / "test_dataset.json"
MIN_RECOMMENDED_QUERIES = 20
RAG_INTENTS = {"legal_query", "conceptual_question", "document_query", "bug_query"}
MEMORY_INTENT_PREFIX = "memory_"


def load_dataset(path: str = None) -> list:
    p = Path(path) if path else DATASET_PATH
    if not p.exists():
        logger.error("Dataset not found: %s", p)
        sys.exit(1)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _detect_scenarios(dataset: list) -> list:
    scenarios = set()
    for item in dataset:
        runs = item.get("runs")
        if isinstance(runs, dict):
            scenarios.update(str(k) for k in runs.keys())
    if not scenarios:
        scenarios = {"legacy"}
    return sorted(scenarios)


def _sanitize_retrieved_ids(retrieved_ids: list, *, exclude_noise: bool, noise_prefixes: list[str]) -> list:
    if not exclude_noise:
        return [str(x) for x in retrieved_ids]
    cleaned = []
    for doc_id in retrieved_ids:
        sid = str(doc_id)
        if any(sid.startswith(prefix) for prefix in noise_prefixes):
            continue
        cleaned.append(sid)
    return cleaned


def _build_queries_data(
    dataset: list,
    scenario: str,
    *,
    exclude_noise: bool = False,
    noise_prefixes: list[str] | None = None,
) -> list:
    noise_prefixes = noise_prefixes or ["exa_", "web_"]
    queries_data = []
    for item in dataset:
        query = item.get("query", "")
        relevant_ids = item.get("relevant_ids", [])

        retrieved_ids = item.get("retrieved_ids")
        if retrieved_ids is None:
            runs = item.get("runs", {})
            if isinstance(runs, dict):
                retrieved_ids = runs.get(scenario)
                if retrieved_ids is None:
                    retrieved_ids = (
                        runs.get("reranker_top5")
                        or runs.get("exa_fallback_top5")
                        or runs.get("baseline")
                        or []
                    )
            else:
                retrieved_ids = []

        retrieved_ids = _sanitize_retrieved_ids(
            list(retrieved_ids or []),
            exclude_noise=exclude_noise,
            noise_prefixes=noise_prefixes,
        )

        queries_data.append(
            {
                "query": query,
                "query_id": item.get("id") or item.get("query_id") or query,
                "language": item.get("language", "unknown"),
                "intent": item.get("intent", "unknown"),
                "retrieved_ids": retrieved_ids,
                "relevant_ids": relevant_ids,
            }
        )
    return queries_data


def _group_and_report(queries_data: list, k: int, field: str) -> dict:
    grouped = {}
    for item in queries_data:
        key = item.get(field, "unknown")
        grouped.setdefault(key, []).append(item)

    out = {}
    for key, rows in grouped.items():
        out[key] = compute_retrieval_report(rows, k=k)["aggregate"]
    return out


def _compute_clean_breakdowns(queries_data: list, k: int) -> dict:
    rag_rows = [q for q in queries_data if q.get("intent") in RAG_INTENTS]
    memory_rows = [
        q for q in queries_data if str(q.get("intent", "")).startswith(MEMORY_INTENT_PREFIX)
    ]

    out = {}
    if rag_rows:
        out["rag_only"] = compute_retrieval_report(rag_rows, k=k)["aggregate"]
    if memory_rows:
        out["memory_only"] = compute_retrieval_report(memory_rows, k=k)["aggregate"]
    return out


def _filter_by_intent_scope(queries_data: list, intent_scope: str) -> list:
    if intent_scope == "all":
        return queries_data
    if intent_scope == "rag":
        return [q for q in queries_data if q.get("intent") in RAG_INTENTS]
    if intent_scope == "memory":
        return [
            q for q in queries_data if str(q.get("intent", "")).startswith(MEMORY_INTENT_PREFIX)
        ]
    return queries_data


def run_generation_evaluation(dataset: list, scenario: str) -> dict:
    lang_groups = {}
    skipped = 0

    for item in dataset:
        reference = item.get("reference_answer")
        if not reference:
            skipped += 1
            continue

        candidate = item.get("candidate_answer")
        if candidate is None:
            candidates_map = item.get("candidate_answers", {})
            if isinstance(candidates_map, dict):
                candidate = candidates_map.get(scenario)
                if candidate is None:
                    candidate = (
                        candidates_map.get("reranker_top5")
                        or candidates_map.get("exa_fallback_top5")
                        or candidates_map.get("baseline")
                    )

        if not candidate:
            skipped += 1
            continue

        lang = item.get("language", "en")
        if lang not in lang_groups:
            lang_groups[lang] = {"references": [], "candidates": []}
        lang_groups[lang]["references"].append(reference)
        lang_groups[lang]["candidates"].append(candidate)

    results = {}
    for lang, data in lang_groups.items():
        try:
            scores = compute_bert_score(
                references=data["references"],
                candidates=data["candidates"],
                lang=lang,
            )
            results[lang] = scores
        except Exception as e:
            logger.warning("BERTScore failed for lang=%s: %s", lang, e)
            results[lang] = {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    if results:
        avg_f1 = sum(r["f1"] for r in results.values()) / len(results)
        avg_p = sum(r["precision"] for r in results.values()) / len(results)
        avg_r = sum(r["recall"] for r in results.values()) / len(results)
    else:
        avg_f1, avg_p, avg_r = 0.0, 0.0, 0.0

    return {
        "overall": {
            "precision": round(avg_p, 4),
            "recall": round(avg_r, 4),
            "f1": round(avg_f1, 4),
        },
        "per_language": results,
        "num_scored_pairs": sum(len(v["references"]) for v in lang_groups.values()),
        "num_skipped_pairs": skipped,
    }


def _append_markdown_run_log(
    log_path: Path,
    *,
    args: argparse.Namespace,
    config: dict,
    retrieval_report: dict,
    generation_report: dict,
    scenario_comparison: dict,
    warnings: list[str],
    output_path: Path,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if not log_path.exists():
        header = [
            "# Evaluation Run Log",
            "",
            "This file is automatically updated after each evaluation run.",
            "",
        ]
        log_path.write_text("\n".join(header), encoding="utf-8")

    agg = retrieval_report.get("aggregate", {})
    precision = float(agg.get("precision_at_k", 0.0))
    recall = float(agg.get("recall_at_k", 0.0))
    mrr = float(agg.get("mrr", 0.0))
    failures = len(retrieval_report.get("failure_cases", []))

    b_overall = generation_report.get("overall", {}) if isinstance(generation_report, dict) else {}
    b_p = float(b_overall.get("precision", 0.0))
    b_r = float(b_overall.get("recall", 0.0))
    b_f1 = float(b_overall.get("f1", 0.0))

    lines = [
        "## Run " + datetime.now().isoformat(timespec="seconds"),
        "",
        "- Dataset: " + str(args.dataset or DATASET_PATH),
        "- Scenario: " + str(args.scenario),
        "- Intent scope: " + str(args.intent_scope),
        "- Exclude noise: " + str(args.exclude_noise),
        "- k: " + str(args.k),
        "- JSON report: " + str(output_path),
        "",
        "```text",
        "-- Evaluation Summary --",
        f"  Precision@{args.k}: {precision:.4f}",
        f"  Recall@{args.k}:    {recall:.4f}",
        f"  MRR:               {mrr:.4f}",
        f"  Failure cases:     {failures}",
        "```",
        "",
    ]

    if not args.skip_bertscore:
        lines.extend(
            [
                "- BERTScore overall: "
                + f"P={b_p:.4f} R={b_r:.4f} F1={b_f1:.4f}",
                "",
            ]
        )

    if scenario_comparison:
        lines.append("### Scenario comparison")
        lines.append("")
        lines.append("| Scenario | Precision@k | Recall@k | MRR |")
        lines.append("|---|---:|---:|---:|")
        for scenario, vals in sorted(scenario_comparison.items()):
            s_p = float(vals.get("precision_at_k", 0.0))
            s_r = float(vals.get("recall_at_k", 0.0))
            s_mrr = float(vals.get("mrr", 0.0))
            lines.append(f"| {scenario} | {s_p:.4f} | {s_r:.4f} | {s_mrr:.4f} |")
        lines.append("")

    if warnings:
        lines.append("### Warnings")
        lines.append("")
        for warning in warnings:
            lines.append("- " + str(warning))
        lines.append("")

    lines.extend(
        [
            "### Configuration",
            "",
            "```json",
            json.dumps(config, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Run chatbot evaluation")
    parser.add_argument("--output", "-o", default="reports/evaluation_report.json")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--scenario", default="reranker_top5")
    parser.add_argument("--compare-scenarios", action="store_true")
    parser.add_argument(
        "--scenario-reports-dir",
        default=None,
        help="Optional directory where per-scenario JSON reports are written",
    )
    parser.add_argument("--exclude-noise", action="store_true")
    parser.add_argument("--noise-prefixes", default="exa_,web_")
    parser.add_argument("--intent-scope", choices=["all", "rag", "memory"], default="all")
    parser.add_argument("--skip-bertscore", action="store_true")
    parser.add_argument(
        "--run-log-markdown",
        default="reports/evaluation_run_log.md",
        help="Markdown file that is updated after each run with terminal summary",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Chatbot Evaluation Runner")
    logger.info("=" * 60)

    dataset = load_dataset(args.dataset)
    logger.info("Loaded %d evaluation queries", len(dataset))

    available_scenarios = _detect_scenarios(dataset)
    noise_prefixes = [p.strip() for p in args.noise_prefixes.split(",") if p.strip()]

    config = {
        "top_k": args.k,
        "dataset_size": len(dataset),
        "timestamp": datetime.now().isoformat(),
        "scenario": args.scenario,
        "intent_scope": args.intent_scope,
        "exclude_noise": args.exclude_noise,
        "noise_prefixes": noise_prefixes,
        "available_scenarios": available_scenarios,
        "reranker": "cosine_similarity",
        "embedding_model": "BAAI/bge-m3",
        "retrieval_method": "hybrid_rrf",
    }

    warnings = []
    if len(dataset) < MIN_RECOMMENDED_QUERIES:
        warnings.append(
            f"Dataset is small ({len(dataset)} queries). Recommended >= {MIN_RECOMMENDED_QUERIES} for stable metrics."
        )
    if args.scenario not in available_scenarios and "legacy" not in available_scenarios:
        warnings.append(
            f"Scenario '{args.scenario}' not found in dataset runs; fallback resolution was used."
        )

    logger.info(
        "Running retrieval evaluation (k=%d, scenario=%s, scope=%s, exclude_noise=%s)...",
        args.k,
        args.scenario,
        args.intent_scope,
        args.exclude_noise,
    )

    selected_queries = _build_queries_data(
        dataset,
        args.scenario,
        exclude_noise=args.exclude_noise,
        noise_prefixes=noise_prefixes,
    )
    selected_queries = _filter_by_intent_scope(selected_queries, args.intent_scope)

    retrieval_report = compute_retrieval_report(selected_queries, k=args.k)
    retrieval_report["per_language"] = _group_and_report(selected_queries, k=args.k, field="language")
    retrieval_report["per_intent"] = _group_and_report(selected_queries, k=args.k, field="intent")
    clean_breakdowns = _compute_clean_breakdowns(selected_queries, k=args.k)

    logger.info(
        "Retrieval: P@%d=%.4f  R@%d=%.4f  MRR=%.4f",
        args.k,
        retrieval_report["aggregate"]["precision_at_k"],
        args.k,
        retrieval_report["aggregate"]["recall_at_k"],
        retrieval_report["aggregate"]["mrr"],
    )

    scenario_comparison = {}
    scenario_reports_dir = Path(args.scenario_reports_dir) if args.scenario_reports_dir else None
    if scenario_reports_dir:
        scenario_reports_dir.mkdir(parents=True, exist_ok=True)

    if args.compare_scenarios:
        for scenario in available_scenarios:
            qrows = _build_queries_data(
                dataset,
                scenario,
                exclude_noise=args.exclude_noise,
                noise_prefixes=noise_prefixes,
            )
            qrows = _filter_by_intent_scope(qrows, args.intent_scope)
            scenario_report = compute_retrieval_report(qrows, k=args.k)
            scenario_report["per_language"] = _group_and_report(qrows, k=args.k, field="language")
            scenario_report["per_intent"] = _group_and_report(qrows, k=args.k, field="intent")

            scenario_comparison[scenario] = scenario_report["aggregate"]

            if scenario_reports_dir:
                scenario_payload = {
                    "configuration": {
                        **config,
                        "scenario": scenario,
                    },
                    "warnings": warnings,
                    "retrieval": scenario_report,
                }
                scenario_file = scenario_reports_dir / f"evaluation_{scenario}.json"
                with open(scenario_file, "w", encoding="utf-8") as sf:
                    json.dump(scenario_payload, sf, ensure_ascii=False, indent=2)
                logger.info("Per-scenario report saved: %s", scenario_file)

    # Always save selected-scenario report when requested, even without compare mode.
    if scenario_reports_dir and not args.compare_scenarios:
        selected_payload = {
            "configuration": config,
            "warnings": warnings,
            "retrieval": retrieval_report,
        }
        selected_file = scenario_reports_dir / f"evaluation_{args.scenario}.json"
        with open(selected_file, "w", encoding="utf-8") as sf:
            json.dump(selected_payload, sf, ensure_ascii=False, indent=2)
        logger.info("Per-scenario report saved: %s", selected_file)

    generation_report = {"overall": {}, "per_language": {}}
    if not args.skip_bertscore:
        logger.info("Running BERTScore evaluation...")
        generation_report = run_generation_evaluation(dataset, scenario=args.scenario)
        logger.info(
            "BERTScore (overall): P=%.4f  R=%.4f  F1=%.4f",
            generation_report["overall"]["precision"],
            generation_report["overall"]["recall"],
            generation_report["overall"]["f1"],
        )
    else:
        logger.info("Skipping BERTScore (--skip-bertscore flag)")

    report = {
        "configuration": config,
        "warnings": warnings,
        "retrieval": retrieval_report,
        "clean_breakdowns": clean_breakdowns,
        "scenario_comparison": scenario_comparison,
        "generation_bertscore": generation_report,
        "failure_cases": retrieval_report.get("failure_cases", []),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if args.run_log_markdown:
        _append_markdown_run_log(
            Path(args.run_log_markdown),
            args=args,
            config=config,
            retrieval_report=retrieval_report,
            generation_report=generation_report,
            scenario_comparison=scenario_comparison,
            warnings=warnings,
            output_path=output_path,
        )
        logger.info("Run markdown log updated: %s", args.run_log_markdown)

    logger.info("Report saved to: %s", output_path)
    logger.info("=" * 60)

    print("\n-- Evaluation Summary --")
    print(f"  Precision@{args.k}: {retrieval_report['aggregate']['precision_at_k']:.4f}")
    print(f"  Recall@{args.k}:    {retrieval_report['aggregate']['recall_at_k']:.4f}")
    print(f"  MRR:               {retrieval_report['aggregate']['mrr']:.4f}")
    print(f"  Failure cases:     {len(retrieval_report.get('failure_cases', []))}")


if __name__ == "__main__":
    main()
