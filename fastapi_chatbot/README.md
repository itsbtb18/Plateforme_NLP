# NLP Platform Chatbot (FastAPI)

Production-grade multilingual RAG service for legal, platform, and user-document question answering.

This README reflects the current codebase architecture and runtime behavior.

## Overview

The FastAPI chatbot is the intelligence layer behind the Django frontend. It provides:

1. Multilingual conversational QA (Arabic, French, English)
2. Intent-aware routing
3. Hybrid retrieval (dense + sparse + fusion + rerank)
4. User document ingestion and document-grounded QA
5. Controlled web search channels
6. Faithfulness verification before final response
7. Session lifecycle and persistent chat history

## Architecture (Current)

Pipeline used for a conversational request:

1. Contextual query rewriting (for multi-turn follow-ups)
2. Intent classification (LLM-first with fallback logic)
3. Routing policy selection
4. Retrieval from one or more channels:
- Internal corpora (Qdrant collections)
- User documents (owner/session scoped)
- Controlled web retrieval (policy-dependent)
5. Hybrid fusion + deduplication + semantic reranking
6. Context assembly
7. LLM answer generation
8. Faithfulness verification
9. Final answer or safe fallback
10. Session/message persistence

## Core Stack

1. API framework: FastAPI (async)
2. LLM provider: Groq
- User-facing model: `llama-3.3-70b-versatile`
- Internal model: `llama-3.1-8b-instant`
3. Embeddings: `BAAI/bge-m3` (1024 dimensions)
4. Vector DB: Qdrant
5. Relational DB: PostgreSQL
6. Search: BM25 (hybrid retrieval) + Elasticsearch integration
7. Queue/background tasks: Celery + Redis
8. Document extraction: PDF/DOCX/XLSX/TXT processors (Docling-enabled pipeline)

## Service Structure

Top-level modules:

1. `app/main.py`: API endpoints and lifecycle
2. `app/services/chat_logic.py`: end-to-end RAG orchestration
3. `app/services/classifier/*`: intent classification
4. `app/services/router/*`: intent-to-source routing
5. `app/services/retrieval/*`: hybrid search, filters, reranking
6. `app/services/llm/*`: LLM client + prompt policies
7. `app/services/faithfulness.py`: hallucination/faithfulness guard
8. `app/services/documents/*`: upload, processing, embeddings
9. `app/services/web/*`: Exa/Tavily integration and web policies
10. `app/services/memory/*`: session/history memory management
11. `app/ingestion/*`: corpus ingestion and reindexing scripts
12. `app/tasks/*`: asynchronous Celery tasks
13. `evaluation/*`: metrics and scenario-based evaluation runner

## Runtime Dependencies

Expected backing services:

1. PostgreSQL
2. Redis
3. Qdrant
4. Elasticsearch (optional for platform lexical/entity operations)

The FastAPI lifespan does:

1. DB init
2. Qdrant collection checks
3. non-blocking warmups:
- embedding model
- LLM client
- BM25 index population

## Environment Variables

Defined in `app/config.py` (main ones):

1. Database and stores
- `DATABASE_URL`
- `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_GRPC_PORT`, `QDRANT_PREFER_GRPC`
- `ELASTICSEARCH_HOST`
- `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`

2. LLM
- `GROQ_API_KEY`, `GROQ_MODEL`
- `GROQ_INTERNAL_API_KEY`, `GROQ_INTERNAL_MODEL`

3. Embeddings
- `EMBEDDING_MODEL`
- `EMBEDDING_DIMENSION`

4. Web search
- `EXA_API_KEY`, `EXA_ENABLED`
- `TAVILY_API_KEY`, `TAVILY_ENABLED`

## API Endpoints (Current)

Health:

1. `GET /health`
2. `GET /warmup`

Knowledge retrieval / conversation:

1. `POST /conversation`
2. `POST /conversation/stream` (SSE)
3. `POST /query`
4. `POST /legal_search`

Platform queries:

1. `POST /platform/search`
2. `GET /platform/stats`
3. `GET /platform/articles`
4. `POST /platform/entity_explain`
5. `POST /platform/document_ingest`

User documents:

1. `POST /upload_document`
2. `GET /document_status/{document_id}`
3. `GET /documents/{session_id}`
4. `POST /ask_document`

Web search:

1. `POST /web/search`
2. `POST /web/search/stream` (SSE)

Sessions:

1. `POST /sessions`
2. `GET /sessions`
3. `GET /sessions/{session_id}/history`
4. `PATCH /sessions/{session_id}/title`
5. `POST /sessions/{session_id}/end`
6. `DELETE /sessions/{session_id}`

Legacy-compatible endpoints also exist (`/start_conversation`, `/end_conversation/{id}`, `/upload_pdf`, `/ask`).

## Local / Container Run

If this service is run via docker-compose, use service names instead of container IDs.

Examples:

1. Open API docs
- `http://localhost:8001/docs` (or mapped FastAPI port in your compose file)

2. Health check
- `curl http://localhost:8001/health`

## Reindexing and Ingestion

Master reindex script:

- module: `app.ingestion.reindex_all`
- options:
1. `--only {nlp,platform,resources,legal}`
2. `--no-wipe`

Recommended commands (compose service name `fastapi`):

1. Full reindex (wipe + rebuild):
```bash
docker-compose exec -T fastapi python -m app.ingestion.reindex_all
```

2. Reindex only legal:
```bash
docker-compose exec -T fastapi python -m app.ingestion.reindex_all --only legal
```

3. Append/update without wipe:
```bash
docker-compose exec -T fastapi python -m app.ingestion.reindex_all --only legal --no-wipe
```

Notes:

1. Reindexing is CPU-intensive.
2. Script includes conservative batching and sleep intervals.
3. Prefer running one heavy embedding/reindex job at a time.

## Evaluation

Evaluation entrypoint:

- `evaluation/runner.py`

Supports:

1. Retrieval metrics: Precision@k, Recall@k, MRR
2. Generation metric: BERTScore
3. Scenario comparison (`baseline`, `reranker_top5`, `exa_fallback_top5`)
4. Intent scoping (`all`, `rag`, `memory`)
5. Noise filtering for web/Exa IDs
6. JSON reports and markdown run log

Examples:

1. Run default evaluation:
```bash
docker-compose exec -T fastapi python evaluation/runner.py --output reports/evaluation_report.json
```

2. Compare scenarios:
```bash
docker-compose exec -T fastapi python evaluation/runner.py --compare-scenarios --scenario reranker_top5
```

3. Run on DB-built dataset:
```bash
docker-compose exec -T fastapi python evaluation/runner.py --dataset evaluation/test_dataset_db.json --output reports/evaluation_report_db.json
```

4. Exclude web noise and skip BERTScore:
```bash
docker-compose exec -T fastapi python evaluation/runner.py --exclude-noise --skip-bertscore
```

## Notes on Web Search

Two web channels are present:

1. Controlled retrieval fallback in the main RAG pipeline (policy-driven)
2. User-triggered web mode endpoints (`/web/search`, `/web/search/stream`)

In both cases, web content should be treated as evidence candidates and not as unconditional final truth.

## Versioning

FastAPI app reports version `4.0.0` in service metadata.
