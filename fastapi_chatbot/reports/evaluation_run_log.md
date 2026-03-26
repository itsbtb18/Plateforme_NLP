# Evaluation Run Log

This file is automatically updated after each evaluation run.
## Run 2026-03-24T18:19:56

- Dataset: /app/evaluation/test_dataset.json
- Scenario: exa_fallback_top5
- Intent scope: rag
- Exclude noise: True
- k: 5
- JSON report: reports/evaluation_report_db_clean.json

```text
-- Evaluation Summary --
  Precision@5: 0.4000
  Recall@5:    1.0000
  MRR:               1.0000
  Failure cases:     0
```

- BERTScore overall: P=0.8188 R=0.8172 F1=0.8179

### Scenario comparison

| Scenario | Precision@k | Recall@k | MRR |
|---|---:|---:|---:|
| baseline | 0.2000 | 0.5000 | 0.8750 |
| exa_fallback_top5 | 0.4000 | 1.0000 | 1.0000 |
| reranker_top5 | 0.4000 | 1.0000 | 1.0000 |

### Configuration

```json
{
  "top_k": 5,
  "dataset_size": 21,
  "timestamp": "2026-03-24T18:19:23.644476",
  "scenario": "exa_fallback_top5",
  "intent_scope": "rag",
  "exclude_noise": true,
  "noise_prefixes": [
    "exa_",
    "web_"
  ],
  "available_scenarios": [
    "baseline",
    "exa_fallback_top5",
    "reranker_top5"
  ],
  "reranker": "cosine_similarity",
  "embedding_model": "BAAI/bge-m3",
  "retrieval_method": "hybrid_rrf"
}
```
## Run 2026-03-24T18:33:22

- Dataset: evaluation/test_dataset_db.json
- Scenario: exa_fallback_top5
- Intent scope: rag
- Exclude noise: True
- k: 5
- JSON report: reports/evaluation_report_db_clean.json

```text
-- Evaluation Summary --
  Precision@5: 0.7524
  Recall@5:    0.9405
  MRR:               0.8786
  Failure cases:     0
```

- BERTScore overall: P=0.9710 R=0.9250 F1=0.9472

### Scenario comparison

| Scenario | Precision@k | Recall@k | MRR |
|---|---:|---:|---:|
| baseline | 0.4086 | 0.5107 | 0.7190 |
| exa_fallback_top5 | 0.7524 | 0.9405 | 0.8786 |
| reranker_top5 | 0.8000 | 1.0000 | 0.8810 |

### Configuration

```json
{
  "top_k": 5,
  "dataset_size": 210,
  "timestamp": "2026-03-24T18:20:44.403228",
  "scenario": "exa_fallback_top5",
  "intent_scope": "rag",
  "exclude_noise": true,
  "noise_prefixes": [
    "exa_",
    "web_"
  ],
  "available_scenarios": [
    "baseline",
    "exa_fallback_top5",
    "reranker_top5"
  ],
  "reranker": "cosine_similarity",
  "embedding_model": "BAAI/bge-m3",
  "retrieval_method": "hybrid_rrf"
}
```
