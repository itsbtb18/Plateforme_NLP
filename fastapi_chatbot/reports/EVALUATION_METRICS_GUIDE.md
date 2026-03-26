# Evaluation Metrics Guide

This guide explains the retrieval and generation metrics used in the chatbot evaluation pipeline, how the evaluation process works end-to-end, and which datasets are used.

## 1. Retrieval Metrics

### Precision@k
Definition:

$$
P@k = \frac{\#\{\text{relevant docs in top-k}\}}{k}
$$

Interpretation:
- High `P@k` means top results are mostly relevant.
- Low `P@k` means many non-relevant items in top results.

Example at `k=5`:
- top-5 contains 4 relevant docs -> `P@5 = 4/5 = 0.8`.

### Recall@k
Definition:

$$
R@k = \frac{\#\{\text{relevant docs in top-k}\}}{\#\{\text{all relevant docs}\}}
$$

Interpretation:
- High `R@k` means the system recovers most relevant docs.
- Low `R@k` means many relevant docs are missing from top-k.

Important note:
- If you define many relevant docs per query, recall is harder to maximize.

### MRR (Mean Reciprocal Rank)
Per query reciprocal rank:

$$
RR = \frac{1}{\text{rank of first relevant doc}}
$$

Aggregate MRR:

$$
MRR = \frac{1}{Q} \sum_{i=1}^{Q} RR_i
$$

Interpretation:
- `MRR` rewards putting at least one relevant doc very early.
- `MRR = 1.0` means first relevant doc is always rank 1.

## 2. Generation Metric

### BERTScore
BERTScore compares semantic similarity between reference answers and generated answers.

Outputs:
- `precision`
- `recall`
- `f1`

Interpretation:
- Higher `F1` usually indicates better semantic alignment.
- BERTScore is semantic, not strict lexical overlap.

## 3. Evaluation Process (End-to-End)

The evaluation process has two phases.

### Phase A: Build evaluation dataset from PostgreSQL

Script:
- `evaluation/build_dataset_from_db.py`

What it does:
1. Pulls records from:
  - `legal_documents`
  - `nlp_knowledge`
2. Generates multilingual queries (Arabic/French/English) from template families.
3. Creates relevance labels (`relevant_ids`) per query.
4. Creates scenario runs (`baseline`, `exa_fallback_top5`, `reranker_top5`).
5. Writes JSON dataset file (default: `evaluation/test_dataset_db.json`).

### Phase B: Run metric computation

Script:
- `evaluation/runner.py`

What it does:
1. Loads the dataset JSON.
2. Selects one scenario (or compares all scenarios).
3. Optionally removes noise IDs (`exa_`, `web_`) with `--exclude-noise`.
4. Filters by intent scope (`all`, `rag`, `memory`).
5. Computes retrieval metrics (`P@k`, `R@k`, `MRR`).
6. Computes generation metric (BERTScore) when enabled.
7. Writes:
  - main report JSON
  - per-scenario report JSONs (if `--scenario-reports-dir` is set)

## 4. Datasets Used

There are two common evaluation datasets in this project.

1. Small fixed dataset:
  - `evaluation/test_dataset.json`
  - Useful for quick smoke tests.

2. DB-derived large dataset:
  - `evaluation/test_dataset_db.json`
  - Built from real project data in PostgreSQL.
  - Recommended for realistic benchmarking.

### DB-Derived dataset content

Sources:
- Legal domain queries from `legal_documents`.
- NLP/conceptual queries from `nlp_knowledge`.

Each row has fields like:
- `id`: query identifier
- `query`: evaluation query text
- `language`: `ar|fr|en`
- `intent`: e.g. `legal_query`, `conceptual_question`
- `relevant_ids`: ground-truth doc IDs
- `runs`: scenario-specific ranked IDs
- `reference_answer`: expected semantic answer reference
- `candidate_answers`: scenario-specific generation candidates

### Why a score of `1.0` can happen

`1.0` is mathematically possible, but often suspicious at scale.

It usually means one of these is true:
1. The synthetic ranking is too easy (relevant docs always first).
2. The number of relevant docs per query is too low.
3. The run definition for a scenario is overly optimistic.

In this project, scenario generation was adjusted so strong scenarios are not always perfect, which gives more realistic values.

## 5. How To Evaluate

From project root:

```bash
cd /home/dahmane/dev/Plateforme_NLP
```

### A. Build DB-backed dataset

```bash
docker-compose exec -T fastapi python evaluation/build_dataset_from_db.py \
  --output evaluation/test_dataset_db.json \
  --legal-limit 120 \
  --nlp-limit 90 \
  --seed 42 \
  --max-relevant-per-query 4
```

### B. Run full evaluation with BERTScore and per-scenario JSON outputs

```bash
docker-compose exec -T fastapi python evaluation/runner.py \
  --dataset evaluation/test_dataset_db.json \
  --scenario exa_fallback_top5 \
  --compare-scenarios \
  --exclude-noise \
  --intent-scope rag \
  --scenario-reports-dir reports/scenario_reports \
  --output reports/evaluation_report_db_clean.json
```

This produces:
- Main report: `reports/evaluation_report_db_clean.json`
- Per-scenario reports:
  - `reports/scenario_reports/evaluation_baseline.json`
  - `reports/scenario_reports/evaluation_exa_fallback_top5.json`
  - `reports/scenario_reports/evaluation_reranker_top5.json`

## 6. Practical Reading of Results

Use all metrics together:
- `P@k` high + `R@k` high + `MRR` high: strong ranking quality.
- `MRR` high but `P@k` low: first hit is good, but top-k still noisy.
- `P@k` high but `R@k` low: very clean top-k, but misses many relevant docs.

For this project:
- If web noise is a concern, run with `--exclude-noise`.
- For RAG retrieval quality only, use `--intent-scope rag`.
- Keep the same dataset seed and limits for fair comparisons over time.

Sanity checks before trusting results:
1. Compare `baseline` vs `exa_fallback_top5` vs `reranker_top5`.
2. Ensure reranker is better, not identical by construction.
3. Check `failure_cases` count and inspect examples.
4. Track metric changes over multiple runs, not one run.

## 7. Recommended Evaluation Workflow

1. Generate dataset from DB (fixed seed).
2. Run evaluation with scenario comparison.
3. Save per-scenario JSON files.
4. Compare deltas in `P@k`, `R@k`, `MRR`, and BERTScore `F1`.
5. Investigate failure cases from report before changing retrieval logic.

## 8. Interpreting Good Targets

Targets vary by dataset difficulty.

For this DB-derived benchmark (RAG scope, top-5):
- `P@5` around `0.65-0.85` can be strong.
- `R@5` near `0.8+` is generally good when each query has multiple relevant docs.
- `MRR` above `0.8` suggests relevant docs appear early.

Avoid optimizing only for one metric. The best system balances precision, recall, and ranking quality.
