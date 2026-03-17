# Arabic NLP Platform — Chatbot Module

## Overview

The chatbot is a **RAG-based (Retrieval-Augmented Generation) conversational AI** system built for the Arabic NLP Research Platform. It helps researchers and students navigate the platform, explore Arabic NLP concepts, query legal frameworks, upload and analyse documents, and search platform content — all in **Arabic, French, and English**.

The system is split into two layers:

| Layer | Technology | Role |
|-------|-----------|------|
| **Backend API** | FastAPI (Python 3.11) | RAG pipeline, LLM inference, vector search, document processing |
| **Frontend Proxy** | Django (Plateforme) | Authentication, UI rendering, session bridging, rate limiting |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         User Browser                             │
│                    (chat.html — JavaScript)                       │
└────────────────┬─────────────────────────────────────────────────┘
                 │  HTTP (JSON)
                 ▼
┌──────────────────────────────────────────────────────────────────┐
│              Django — chatbot/views.py                            │
│  • Authentication (@login_required)                              │
│  • Rate limiting (30 req/min per user)                           │
│  • Mode routing (conversation, quick, legal, platform, upload,   │
│    ask_document)                                                 │
│  • File validation (PDF, DOCX, TXT, XLSX — max 20 MB)           │
│  • Session bridging (Django ChatSession ↔ FastAPI session_id)    │
│  • User profile injection (name, institution, speciality)        │
└────────────────┬─────────────────────────────────────────────────┘
                 │  HTTP (internal network)
                 ▼
┌──────────────────────────────────────────────────────────────────┐
│              FastAPI — app/main.py (v4.0.0)                      │
│  • 18+ REST endpoints                                            │
│  • RAG orchestration via ChatLogic                               │
│  • Intent classification → query routing → LLM generation        │
│  • Async SQLAlchemy + Qdrant + Elasticsearch                     │
└───┬──────────┬──────────┬──────────┬──────────┬──────────────────┘
    │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────────┐
│Postgres│ │ Qdrant │ │Elastic │ │ Redis  │ │ Celery Worker  │
│(pgvec) │ │(vector)│ │(search)│ │(cache) │ │(doc processing)│
└────────┘ └────────┘ └────────┘ └────────┘ └────────────────┘
                                                    │
                                                    ▼
                                              ┌──────────┐
                                              │ Groq API │
                                              │(LLaMA 3) │
                                              └──────────┘
```

---

## RAG Pipeline (Per Conversation Turn)

The core pipeline is implemented in `app/services/chat_logic.py`:

```
User Question
     │
     ▼
1. Language Detection ─── langdetect + Arabic script heuristic → ar / fr / en
     │
     ▼
2. Intent Classification ─── heuristic pattern matching (7 intents)
     │                        • conceptual_question
     │                        • platform_query
     │                        • legal_query
     │                        • document_query
     │                        • user_query
     │                        • metadata_query
     │                        • general_knowledge
     │
     ▼
3. Query Routing ─── directs to the correct data source(s)
     │   ├── conceptual_question → Qdrant hybrid search (all collections)
     │   ├── platform_query     → Elasticsearch + PostgreSQL
     │   ├── legal_query        → Qdrant (legal_documents collection)
     │   ├── document_query     → Qdrant (document_chunks, owner-scoped)
     │   ├── user_query         → PostgreSQL (user profile lookup)
     │   ├── metadata_query     → PostgreSQL (platform stats)
     │   └── general_knowledge  → Direct LLM (no retrieval)
     │
     ▼
4. Context Assembly
     │   ├── Retrieved documents (weighted, deduplicated, reranked)
     │   ├── Platform data (verified facts — highest priority)
     │   ├── Navigation hints (platform links)
     │   ├── User profile (injected only for identity queries)
     │   └── Conversation memory (recent messages + rolling summary)
     │
     ▼
5. LLM Generation ─── Groq API (LLaMA 3.3 70B)
     │   ├── Trilingual system prompts (ar / fr / en)
     │   ├── Source-specific rules (legal, platform, etc.)
     │   └── Mandatory rules (no hallucinated dates, source citations, etc.)
     │
     ▼
6. Persist ─── Save user + assistant messages to PostgreSQL
               Auto-title session from first question
```

---

## Knowledge Sources

### 1. Qdrant Vector Collections

Five collections store dense vector embeddings (768-dim, `paraphrase-multilingual-mpnet-base-v2`):

| Collection | Content | Boost |
|-----------|---------|-------|
| `platform_docs` | Platform feature documentation | ×1.10 |
| `nlp_knowledge` | Arabic NLP concepts, terminology, techniques | ×1.00 |
| `resources` | Articles, datasets, projects, tutorials | ×1.00 (+ geo boost) |
| `legal_documents` | GDPR, EU AI Act, Arab data protection, copyright, ethics | ×1.05 |
| `document_chunks` | User-uploaded document chunks (owner-scoped) | ×1.15 |

### 2. Elasticsearch Indices

Mirrors Django's search indices for platform content — courses, tools, corpora, events, projects, institutions, users. Returns direct platform URLs.

### 3. PostgreSQL

Structured data — user profiles, session metadata, platform statistics, navigation.

---

## Hybrid Search & Retrieval

Implemented in `app/services/retrieval/`:

- **Hybrid search** (`hybrid.py`): queries all Qdrant collections in parallel, applies per-source weight boosts and geo-proximity boosts
- **Deduplication** (`reranker.py`): Jaccard similarity at 0.85 threshold removes near-duplicate chunks
- **Reranking** (`reranker.py`): re-encodes top results and computes fresh cosine similarity against the query
- **Filters** (`filters.py`): language, jurisdiction, owner_id, session_id payload filters

---

## Conversation Memory

Managed by `app/services/memory/session.py`:

- Last **20 messages** retained per session (configurable)
- **Token budget**: 1,500 tokens for history, 500 for summary
- **Rolling summarisation**: at 12-message threshold, Celery generates a summary via Groq and stores it on the session
- Token counting on every persisted message

---

## Document Processing

Upload → Celery → Qdrant pipeline:

1. **Upload** (`POST /upload_document`): validates file type/size, extracts raw text (PDF, DOCX, TXT, XLSX)
2. **Celery task** (`app/tasks/document_tasks.py`): chunks text (512 tokens, 64 overlap), generates embeddings, upserts to Qdrant `document_chunks` collection
3. **Query** (`POST /ask_document`): searches only the user's own document chunks in Qdrant, generates answer via Groq

Supported file types: `.pdf`, `.docx`, `.doc`, `.txt`, `.xlsx` (max 20 MB)

---

## Chat Modes

The Django frontend exposes multiple modes through a single `/chatbot/ask/` endpoint:

| Mode | Description | FastAPI Endpoint |
|------|-------------|-----------------|
| `conversation` | Full RAG pipeline with session context | `POST /conversation` |
| `quick` | Stateless quick question (no context) | `POST /query` |
| `legal` | Legal knowledge base search | `POST /legal_search` |
| `platform` | Platform content search (courses, tools, etc.) | `POST /platform/search` |
| `upload` | Upload document for analysis | `POST /upload_document` |
| `ask_document` | Question about uploaded document(s) | `POST /ask_document` |

---

## API Endpoints (FastAPI)

### Knowledge Retrieval
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/conversation` | Full RAG conversation with session memory |
| `POST` | `/query` | Quick stateless question |
| `POST` | `/legal_search` | Legal knowledge base search |

### Platform Queries
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/platform/search` | Search platform content by type |
| `GET` | `/platform/stats` | Platform statistics |
| `GET` | `/platform/articles` | Article lookup by keyword |

### User Documents
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/upload_document` | Upload PDF/DOCX/TXT/XLSX for analysis |
| `GET` | `/document_status/{id}` | Check document processing status |
| `GET` | `/documents/{session_id}` | List documents in a session |
| `POST` | `/ask_document` | Ask question about uploaded documents |

### Session Management
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/sessions` | Create new chat session |
| `GET` | `/sessions` | List user sessions |
| `GET` | `/sessions/{id}/history` | Get session message history |
| `PATCH` | `/sessions/{id}/title` | Rename session |
| `POST` | `/sessions/{id}/end` | End (deactivate) session |
| `DELETE` | `/sessions/{id}` | Delete session and all messages |

### System
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/warmup` | Pre-warm embedding model |

---

## Data Models

### FastAPI (PostgreSQL)

| Model | Table | Purpose |
|-------|-------|---------|
| `PlatformDoc` | `platform_docs` | Platform feature documentation |
| `NLPKnowledge` | `nlp_knowledge` | Arabic NLP concepts and terminology |
| `Resource` | `resources` | Research resources (articles, datasets, etc.) |
| `LegalDocument` | `legal_documents` | Legal/regulatory knowledge base |
| `UserDocument` | `user_documents` | User-uploaded document metadata |
| `DocumentChunk` | `document_chunks` | Individual text chunks (vectors in Qdrant) |
| `ChatSession` | `chat_sessions` | Session tracking with summary and language |
| `ChatMessage` | `chat_messages` | Message history with token counts |

### Django

| Model | Purpose |
|-------|---------|
| `ChatSession` | Mirrors FastAPI sessions, linked to Django User |
| `ChatMessage` | Local message copy for history display |
| `ChatFeedback` | User ratings (1–5) on bot responses |

---

## Project Structure

```
fastapi_chatbot/
├── app/
│   ├── main.py                 # FastAPI app, 18+ endpoints, lifespan
│   ├── config.py               # Pydantic settings (env vars)
│   ├── db.py                   # Async SQLAlchemy engine + migrations
│   ├── models.py               # 8 SQLAlchemy models
│   ├── schemas.py              # Pydantic request/response schemas
│   ├── celery_app.py           # Celery config (3 queues)
│   │
│   ├── services/
│   │   ├── chat_logic.py       # RAG orchestrator (classify → route → generate)
│   │   ├── language.py         # Trilingual language detection
│   │   ├── elasticsearch_service.py  # ES index search (platform content)
│   │   ├── platform_queries.py # PostgreSQL platform data queries
│   │   │
│   │   ├── classifier/         # Intent classification
│   │   │   ├── engine.py       # Heuristic-based classifier (7 intents)
│   │   │   └── patterns.py     # Regex patterns for classification
│   │   │
│   │   ├── router/             # Query routing
│   │   │   └── engine.py       # Routes intents to data sources
│   │   │
│   │   ├── retrieval/          # Vector search & ranking
│   │   │   ├── search.py       # Per-collection Qdrant search
│   │   │   ├── hybrid.py       # Weighted multi-source search
│   │   │   ├── reranker.py     # Deduplication + cosine reranking
│   │   │   └── filters.py      # Qdrant payload filters
│   │   │
│   │   ├── llm/                # LLM inference
│   │   │   ├── client.py       # Groq API client (async)
│   │   │   └── prompts.py      # Trilingual system prompts & rules
│   │   │
│   │   ├── memory/             # Conversation memory
│   │   │   ├── session.py      # Session CRUD + history management
│   │   │   └── tokens.py       # Token estimation
│   │   │
│   │   ├── documents/          # Document processing
│   │   │   ├── service.py      # Upload, status, listing
│   │   │   ├── processor.py    # PDF/DOCX/TXT/XLSX text extraction
│   │   │   └── embeddings.py   # Multilingual sentence-transformer
│   │   │
│   │   └── qdrant/             # Vector database
│   │       ├── client.py       # Qdrant client wrapper
│   │       └── collections.py  # Collection names & payload schemas
│   │
│   ├── tasks/                  # Celery background tasks
│   │   ├── document_tasks.py   # Chunking + embedding generation
│   │   ├── ingestion_tasks.py  # Batch knowledge base ingestion
│   │   ├── summary_tasks.py    # Chat history summarisation
│   │   └── maintenance_tasks.py # Cleanup & reindexing
│   │
│   └── ingestion/              # Knowledge base loaders
│       ├── ingest_platform_docs.py
│       ├── ingest_nlp_knowledge.py
│       ├── ingest_resources.py
│       ├── ingest_nlp_resources.py
│       └── ingest_legal_docs.py
│
├── Dockerfile                  # Multi-stage build (Python 3.11 + PyTorch CPU)
├── requirements.txt            # 20+ dependencies
└── test_*.py                   # Test files
```

```
Plateforme/chatbot/             # Django frontend module
├── views.py                    # Proxy to FastAPI (ask_bot, session mgmt)
├── models.py                   # ChatSession, ChatMessage, ChatFeedback
├── urls.py                     # 7 URL patterns
├── admin.py                    # Django admin registration
└── templates/chatbot/chat.html # Chat UI
```

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API Framework** | FastAPI 0.115 | Async REST API |
| **LLM** | Groq API (LLaMA 3.3 70B) | Text generation |
| **Embeddings** | sentence-transformers (paraphrase-multilingual-mpnet-base-v2) | 768-dim multilingual vectors |
| **Vector DB** | Qdrant 1.12 | Semantic search (5 collections) |
| **Search Engine** | Elasticsearch 8.x | Platform content full-text search |
| **Relational DB** | PostgreSQL + pgvector | Structured data + session state |
| **Task Queue** | Celery + Redis | Document processing, summarisation |
| **Cache** | Redis 7 | Rate limiting, session cache |
| **Web Framework** | Django 5.x | Authentication, UI, frontend proxy |
| **Language Detection** | langdetect + heuristics | ar / fr / en classification |
| **Reverse Proxy** | Nginx | Load balancing, static files |
| **Container** | Docker Compose | Multi-service orchestration |

---

## Docker Services

The chatbot runs as part of an 8-service Docker Compose stack:

| Service | Container | Port |
|---------|-----------|------|
| PostgreSQL (pgvector) | `nlp_postgres` | 5432 |
| Redis | `nlp_redis` | 6379 |
| Qdrant | `nlp_qdrant` | 6333, 6334 (gRPC) |
| Elasticsearch | `nlp_elasticsearch` | 9200 |
| Django | `nlp_django` | 8888→8000 |
| FastAPI | `nlp_fastapi` | 8000 |
| Celery Worker | `nlp_celery_worker` | — |
| Nginx | `nlp_nginx` | 80, 443 |

---

## Configuration

All settings are loaded from environment variables (see `app/config.py`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL async connection string |
| `GROQ_API_KEY` | — | Groq API key (**required, never logged**) |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | LLM model |
| `EMBEDDING_MODEL` | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | Embedding model |
| `QDRANT_HOST` | `qdrant` | Qdrant hostname |
| `ELASTICSEARCH_HOST` | `http://elasticsearch:9200` | Elasticsearch URL |
| `SIMILARITY_THRESHOLD` | `0.35` | Minimum vector similarity score |
| `CHUNK_SIZE` | `512` | Document chunk size (tokens) |
| `CHUNK_OVERLAP` | `64` | Chunk overlap |
| `MAX_UPLOAD_SIZE_MB` | `20` | Max upload file size |
| `HISTORY_SUMMARY_THRESHOLD` | `12` | Messages before summarisation |
| `MAX_HISTORY_MESSAGES` | `20` | Max messages in context window |
| `TOKEN_BUDGET_HISTORY` | `1500` | Token budget for chat history |
| `TOKEN_BUDGET_SUMMARY` | `500` | Token budget for session summary |

---

## Multilingual Support

The chatbot natively supports three languages:

- **Arabic (ar)** — primary language, full Arabic NLP domain expertise
- **French (fr)** — full support with translated prompts and rules
- **English (en)** — full support, default fallback

Language is auto-detected per message using:
1. Arabic Unicode script ratio (≥30% → Arabic)
2. `langdetect` library for French vs English
3. The LLM responds in the same language as the user's question

---

## Security

- All endpoints behind Django `@login_required` authentication
- Rate limiting: 30 requests/minute per user (Django cache)
- File upload validation: type whitelist, size limit
- API key never logged (`GROQ_API_KEY`)
- User email addresses never exposed in LLM responses (enforced via prompt rules)
- Document access scoped by `user_id` (ownership enforcement)
- CORS configured (should be restricted in production)

---

## Celery Task Queues

| Queue | Tasks |
|-------|-------|
| `chatbot` | Chat history summarisation, text summarisation |
| `documents` | Document chunking + embedding, collection reindexing |
| `ingestion` | Batch knowledge base ingestion, web crawling |

Task limits: 10 min soft / 15 min hard timeout, `acks_late` for reliability.

---

## Document Session Isolation

Each chat session is an **isolated document workspace**. Uploaded documents are only accessible within the session they were uploaded to.

- Qdrant filter uses BOTH `owner_id` AND `session_id` (AND logic)
- `document_chunks` excluded from hybrid search — only queried in `document_query` mode
- `document_query` intent requires explicit document references ("in this document", "my PDF", etc.)
- `SOFT_DOCUMENT_PATTERN` disabled — generic verbs no longer trigger document retrieval

## Retrieval Quality Control

| Setting | Value |
|---------|-------|
| `SIMILARITY_THRESHOLD` (global) | 0.65 |
| `nlp_knowledge` per-collection | 0.55 |
| `legal_documents` per-collection | 0.60 |
| `document_chunks` per-collection | 0.65 |
| `platform_docs` / `resources` | 0.50 |
| Context quality filter | 0.60 (below = dropped) |

Clean context injection — no metadata, scores, titles, or source labels passed to LLM.

## LLM Prompt Architecture

- 16 mandatory rules per language (Rule 16: Response Expansion)
- RAG context labelled as "Background knowledge" (not "documents" or "context")
- Structured, detailed, academic-quality answers enforced
- `GROQ_MAX_TOKENS`: 4096 for both RAG and non-RAG modes

---

**Version:** 5.0.0
**Last Updated:** March 2026
