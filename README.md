# Arabic NLP Research Platform

A multi-service platform for Arabic Natural Language Processing research, combining conversational AI, document intelligence, web scraping, and knowledge management into a unified, containerized system.

## Overview

The platform provides researchers and practitioners with tools for:

- **Conversational AI** — multilingual chatbot with RAG, web search, and document Q&A (Arabic, French, English)
- **Document Intelligence** — CV/resume extraction, translation, and summarization via LLM pipelines
- **Knowledge Scraping** — automated ingestion of NLP research papers, events, tools, and institutions
- **Semantic Search** — vector search (Qdrant) and full-text search (Elasticsearch) over a curated corpus
- **Community Features** — forums, projects, direct messaging, notifications, and Q&A

---

## Architecture

```
                         ┌─────────────────────┐
                         │   Nginx (Port 80)   │
                         │   Reverse Proxy     │
                         └──────────┬──────────┘
                                    │
          ┌─────────────────────────┼──────────────────────────┐
          │                         │                          │
   ┌──────▼──────┐          ┌───────▼──────┐         ┌────────▼───────┐
   │   Django    │          │ FastAPI Chat │         │ CV Processing  │
   │  (Port 8888)│          │  (Port 8002) │         │  (Port 8003)   │
   │  Main App   │          │  RAG + LLM   │         │  Resume Extrac.│
   └──────┬──────┘          └───────┬──────┘         └────────┬───────┘
          │                         │                          │
          └──────────────┬──────────┘                          │
                         │              ┌──────────────────────┘
          ┌──────────────▼──────────────▼──────────────┐
          │          Shared Services                    │
          │                                            │
          │  PostgreSQL+pgvector  Redis  Qdrant        │
          │  Elasticsearch        Celery Workers       │
          └────────────────────────────────────────────┘
                         │
          ┌──────────────▼──────────────┐
          │  Translation/Summarization  │
          │     Service (Port 8010)     │
          └─────────────────────────────┘
```

### Services

| Service | Container | Port | Description |
|---|---|---|---|
| Django (Daphne/ASGI) | `nlp_django` | 8888 | Main web application, REST APIs, WebSockets |
| FastAPI Chatbot | `nlp_fastapi` | 8002 | Conversational AI engine with RAG |
| CV Processing | `nlp_cv_processing` | 8003 | Resume extraction and analysis |
| Translation/Summarization | `nlp_translation_summarization` | 8010 | Multi-language document processing |
| PostgreSQL + pgvector | `nlp_postgres` | 5433 | Primary database with vector extension |
| Redis | `nlp_redis` | 6379 | Cache, message broker, task queue |
| Qdrant | `nlp_qdrant` | 6333 | Vector database for semantic search |
| Elasticsearch | `nlp_elasticsearch` | 9200 | Full-text search engine |
| Nginx | `nlp_nginx` | 80, 8001 | Reverse proxy and static file serving |
| Celery Worker | — | — | Background task processing |
| Celery Beat | — | — | Scheduled task runner |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | Django 4.x + Daphne (ASGI), FastAPI |
| LLM providers | Google Gemini, Groq (Llama 3.x) |
| Vector DB | Qdrant |
| Search | Elasticsearch |
| Database | PostgreSQL 15 + pgvector |
| Cache / Queue | Redis 7, Celery |
| Web search | Tavily, Exa |
| Embeddings | BAAI/bge-m3 (1024-dim) |
| Containers | Docker Compose |
| Real-time | Django Channels (WebSockets) |

---

## Getting Started

### Prerequisites

- Docker and Docker Compose v2
- At minimum 8 GB RAM available for Docker
- API keys for at least one LLM provider (Gemini or Groq)

### Setup

**1. Clone and configure environment**

```bash
git clone <repository-url>
cd Plateforme_NLP
cp .env.example .env
```

Edit `.env` and fill in all required values. The minimum required fields are:

```env
POSTGRES_PASSWORD=<strong-random-password>
REDIS_PASSWORD=<strong-random-password>
DJANGO_SECRET_KEY=<50+-character-random-string>
GROQ_API_KEY=<your-groq-key>        # or
GENAI_API_KEY=<your-gemini-key>
```

**2. Start the platform**

```bash
# Minimal stack (Django + DB + Redis + Nginx)
docker compose --profile scraping up -d

# Full stack (adds FastAPI chatbot, Qdrant, Elasticsearch, Celery)
docker compose --profile full up -d

# With task scheduler
docker compose --profile full --profile scheduler up -d
```

**3. Initialize the database**

```bash
docker compose exec django python manage.py migrate
docker compose exec django python manage.py collectstatic --noinput
```

**4. Create an admin user**

```bash
ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=<strong-password> \
  docker compose exec django python create_admin.py
```

**5. Access the platform**

| Interface | URL |
|---|---|
| Main platform | http://localhost |
| Django admin | http://localhost/admin |
| FastAPI chatbot | http://localhost/ai |
| API docs (FastAPI) | http://localhost:8002/docs |
| CV Processing API | http://localhost:8003/docs |

---

## Configuration

All configuration is driven by environment variables. Copy `.env.example` to `.env` and fill in the values. Never commit `.env` to version control.

### Key variable groups

| Group | Variables | Description |
|---|---|---|
| Database | `POSTGRES_*` | PostgreSQL credentials and connection |
| Cache | `REDIS_PASSWORD`, `REDIS_URL` | Redis authentication |
| Django | `DJANGO_SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` | Core Django settings |
| LLM (chat) | `GENAI_API_KEY`, `GROQ_API_KEY` | Chatbot generation |
| LLM (scraping) | `GEMINI_SCRAPING_API_KEY`, `GROQ_SCRAPING_API_KEY` | Content validation |
| LLM (translation) | `TS_GEMINI_API_KEY`, `TS_GROQ_API_KEY` | Translation/summarization |
| Vector store | `QDRANT_API_KEY` | Qdrant authentication |
| Web search | `TAVILY_API_KEY`, `EXA_API_KEY` | RAG web search fallback |
| Email | `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Gmail SMTP (optional) |

See `.env.example` for the full list with descriptions.

---

## Django Apps

| App | Purpose |
|---|---|
| `accounts` | User registration, authentication, profiles |
| `chatbot` | AI chat interface and session management |
| `forum` | Discussion threads and Q&A |
| `projects` | Research project collaboration |
| `institutions` | NLP research institutions directory |
| `resources` | Curated NLP tools, datasets, papers |
| `scraping` | Automated web scraping pipeline |
| `search` | Unified search over all content |
| `evaluation` | AI output scoring and human evaluation |
| `translate` | Translation/summarization proxy to TS service |
| `feed` | Activity feeds and content discovery |
| `events` | Conferences, workshops, and events |
| `QA` | Question & Answer system |
| `notifications` | Real-time notifications (WebSockets) |
| `direct_messages` | User-to-user messaging |

---

## Chatbot Capabilities

The FastAPI chatbot service supports:

- **RAG mode** — retrieves from the platform's curated corpus (legal docs, NLP papers, institutions)
- **Web search mode** — live web search via Tavily (user-triggered)
- **Document Q&A** — upload PDF/DOCX and ask questions
- **Multi-session memory** — conversation history with summarization
- **Multilingual** — Arabic, French, English (auto-detected)
- **Provider fallback** — Gemini → Groq automatic failover

---

## Scraping Pipeline

The scraping system runs as a Celery task and covers:

- ArXiv and Semantic Scholar (research papers)
- NLP conferences and events
- Institution websites
- Government and legal documents
- RSS feeds and listing pages

Content is validated by LLM, deduplicated (Jaccard + semantic similarity), enriched with NER, and indexed into PostgreSQL, Qdrant, and Elasticsearch.

---

## Development

### Running tests

```bash
# FastAPI chatbot tests
cd fastapi_chatbot && pytest

# CV processing tests
cd cv_processing && pytest
```

### Adding scraping sources

Sources are managed via Django admin under the Scraping section, or by adding entries to the database via management commands.

### Logs

```bash
docker compose logs -f django
docker compose logs -f fastapi
docker compose logs -f celery_worker
```

---

## Security Notes

- Never commit `.env` — it is gitignored
- Rotate all API keys if they were ever exposed in git history
- Set `DEBUG=False` in production
- Use strong, unique passwords for `POSTGRES_PASSWORD` and `REDIS_PASSWORD`
- The `DJANGO_SECRET_KEY` must be at least 50 characters and kept secret
- The `ADMIN_PASSWORD` for the create_admin script must be passed via environment variable

---

## License

This project is developed as part of academic NLP research. See `LICENSE` for details.
