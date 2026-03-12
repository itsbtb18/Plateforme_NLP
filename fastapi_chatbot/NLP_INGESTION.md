# NLP Document Ingestion — Setup & Usage Guide

## Overview

The ingestion pipeline processes PDF and XML research papers into the chatbot's knowledge base (PostgreSQL + Qdrant vector store). Documents are chunked, filtered, embedded, and stored for RAG retrieval.

**Key features:**
- Section filtering (skips References, Bibliography, Appendix, Acknowledgments)
- Citation stripping (removes `[1,2]` and `(Author, 2021)` patterns)
- Tiny chunk merging (< 50 tokens merged with neighbours)
- Resume-safe checkpointing (resumes after interruption)
- CPU-safe: 1 document at a time, batch size of 8 embeddings
- Large file fallback: files > 5 MB use lightweight PyPDF2 instead of Docling

---

## Prerequisites

All services must be running:

```bash
cd /path/to/Plateforme_NLP
docker-compose up -d
```

Verify health:

```bash
curl http://localhost:8001/health
# Expected: {"status":"healthy","service":"fastapi-chatbot","version":"4.0.0"}
```

---

## Adding New Documents

1. Place PDF or XML (JATS format) files in `fastapi_chatbot/data/`
2. Run the ingestion command (see below)

---

## Ingestion Commands

All commands run inside the `nlp_fastapi` container:

### Ingest a single file

```bash
docker exec nlp_fastapi python -m app.ingestion.ingest_nlp_resources \
    --file "data/YourPaper.pdf"
```

### Ingest all files in the data/ directory

Processes files smallest-first with automatic checkpointing:

```bash
docker exec nlp_fastapi python -m app.ingestion.ingest_nlp_resources --dir data/
```

### Dry run (preview without writing to DB)

```bash
docker exec nlp_fastapi python -m app.ingestion.ingest_nlp_resources \
    --file "data/YourPaper.pdf" --dry-run
```

### Force re-ingest (ignore checkpoint)

```bash
docker exec nlp_fastapi python -m app.ingestion.ingest_nlp_resources \
    --dir data/ --force
```

### Set difficulty level

```bash
docker exec nlp_fastapi python -m app.ingestion.ingest_nlp_resources \
    --file "data/YourPaper.pdf" --difficulty advanced
```

Options: `beginner`, `intermediate` (default), `advanced`

---

## Cleanup Commands

### Delete only ingested PDF/XML chunks (keep 14 seed rows)

```bash
docker exec nlp_fastapi python -m app.ingestion.cleanup_nlp --pdf-only
```

### Delete ALL NLP data (seeds + chunks)

```bash
docker exec nlp_fastapi python -m app.ingestion.cleanup_nlp --all
```

### Preview what would be deleted

```bash
docker exec nlp_fastapi python -m app.ingestion.cleanup_nlp --pdf-only --dry-run
```

### Reset PostgreSQL ID sequence after cleanup

```bash
docker exec nlp_fastapi python -m app.ingestion.cleanup_nlp --pdf-only --reset-sequence
```

---

## Check Ingestion Status

```bash
docker exec nlp_fastapi python -c "
import asyncio
from app.db import AsyncSessionLocal
from app.models import NLPKnowledge
from sqlalchemy import select, func
async def check():
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(NLPKnowledge.source_file, NLPKnowledge.document_type,
                   func.count(NLPKnowledge.id).label('c'))
            .where(NLPKnowledge.version == 2)
            .group_by(NLPKnowledge.source_file, NLPKnowledge.document_type)
            .order_by(func.count(NLPKnowledge.id))
        )).all()
        total = 0
        for sf, dt, c in rows:
            print(f'  {c:3d} chunks | {dt:8s} | {sf}')
            total += c
        seed = (await db.execute(select(func.count(NLPKnowledge.id))
            .where(NLPKnowledge.version != 2))).scalar()
        print(f'\n  {len(rows)} documents, {total} v2 chunks + {seed} seeds')
asyncio.run(check())
" 2>&1 | grep -v 'sqlalchemy\|INFO\|Engine'
```

---

## Resource Limits

The containers are configured with CPU and memory safety limits:

| Setting | Value | Purpose |
|---------|-------|---------|
| `cpus` | 1.0 | Limit to 1 CPU core |
| `mem_limit` | 2g | Max 2 GB RAM |
| `OMP_NUM_THREADS` | 1 | Disable OpenMP parallelism |
| `MKL_NUM_THREADS` | 1 | Disable MKL parallelism |
| `OPENBLAS_NUM_THREADS` | 1 | Disable OpenBLAS parallelism |
| `TOKENIZERS_PARALLELISM` | false | Disable HuggingFace tokenizer parallelism |
| `TORCH_NUM_THREADS` | 1 | Limit PyTorch to 1 thread |
| `NUMEXPR_MAX_THREADS` | 1 | Limit NumExpr to 1 thread |
| Celery `--concurrency` | 1 | One task at a time |

---

## How File Size Affects Processing

| File Size | Parser Used | Memory Usage | Notes |
|-----------|-------------|-------------|-------|
| < 5 MB | **Docling** (structured) | ~1–2 GB | Full layout analysis, section headings preserved |
| ≥ 5 MB | **PyPDF2** (lightweight) | ~200–500 MB | Text-only extraction, no layout model |

The 5 MB threshold (`LARGE_FILE_THRESHOLD_MB` in `pdf_loader.py`) can be adjusted if your machine has more RAM.

---

## File Types Supported

| Format | Parser | Notes |
|--------|--------|-------|
| `.pdf` | Docling or PyPDF2 | Automatic fallback based on size |
| `.xml` | JATS XML parser | For academic papers in JATS/NLM format |

---

## Document Type Classification

The ingestion script auto-classifies documents based on filename:

| Keyword in filename | Classified as |
|---------------------|---------------|
| survey, review, landscape, evaluating, benchmark | `survey` |
| speech and language processing, jurafsky | `book` |
| tutorial, guide | `tutorial` |
| *(anything else)* | `paper` |

---

## Troubleshooting

### Exit code 137 (OOM killed)

The file is too large for Docling. Lower `LARGE_FILE_THRESHOLD_MB` in `pdf_loader.py` or increase the container memory limit temporarily:

```bash
docker update --memory 4g nlp_fastapi
docker exec nlp_fastapi python -m app.ingestion.ingest_nlp_resources --file "data/large_file.pdf"
docker update --memory 2g nlp_fastapi   # restore after
```

### `rt_detr_v2` / transformers version error

Docling requires `transformers>=4.50`. Update in `requirements.txt` and rebuild:

```bash
docker-compose build fastapi
docker stop nlp_fastapi nlp_celery_worker && docker rm nlp_fastapi nlp_celery_worker
docker-compose up -d --no-deps fastapi celery_worker
```

### `invalid byte sequence for encoding "UTF8": 0x00`

The PDF contains null bytes. This is handled automatically by the pipeline (stripped in `_clean_text`). If it persists, check `pdf_loader.py` line with `text.replace("\\x00", "")`.

### Ingestion interrupted (CPU overload, crash, etc.)

Just re-run the same command — the checkpoint file (`.nlp_ingest_checkpoint.json`) tracks completed files and resumes from where it stopped:

```bash
docker exec nlp_fastapi python -m app.ingestion.ingest_nlp_resources --dir data/
```

### Services down after system freeze

```bash
docker-compose ps                              # check status
docker-compose up -d redis elasticsearch       # restart crashed services
docker-compose restart fastapi celery_worker   # restart app services
```

---

## Currently Ingested Documents (18 files, 1927 chunks)

| Chunks | Type | Document |
|--------|------|----------|
| 20 | paper | Arabic NER Framework (XML) |
| 32 | survey | Arabic NLP Comprehensive Review (XML) |
| 33 | paper | AraBERT |
| 46 | survey | Code-switched Arabic NLP Survey |
| 47 | paper | RAG |
| 48 | survey | Arabic LLMs Landscape |
| 50 | paper | Knowledge Graphs, LLMs & Hallucinations |
| 55 | survey | Evaluating Arabic LLMs |
| 58 | paper | DPS |
| 59 | paper | BERT |
| 67 | paper | CAMeL Tools |
| 80 | paper | Transformers Beyond NLP |
| 99 | survey | Agentic AI Systematic Review |
| 108 | paper | Attention Is All You Need |
| 126 | paper | Arabic QA ML/DL Techniques |
| 189 | paper | From LLM Reasoning to AI Agents |
| 209 | paper | GPT Paper |
| 601 | book | Speech & Language Processing (Jurafsky & Martin) |

---

## LLM Prompt Engineering (ChatGPT-like Behavior)

The chatbot's LLM prompts are defined in `app/services/llm/prompts.py` and enforce a natural, expert-like conversational style. All prompts are trilingual (Arabic, French, English).

### System Prompt Persona

The system prompt defines the assistant as:
> An expert AI assistant specialised in Artificial Intelligence, Natural Language Processing, Machine Learning, and related technical domains. Goal: provide clear, accurate, professional answers in a natural, human-like style similar to ChatGPT.

### Behavior Rules (CRITICAL_RULES — 15 rules per language)

| # | Rule | Description |
|---|------|-------------|
| 1 | Language lock | Respond only in the detected language |
| 2 | Natural style | Sound like a knowledgeable human expert, not mechanical or retrieval-based |
| 3 | No source disclosure | Never mention documents, chunks, similarity scores, or internal system logic |
| 4 | No missing context | Never say "the term is not mentioned", "I don't have context", etc. |
| 5 | Hybrid intelligence | Use internal knowledge silently; fall back to general knowledge when retrieval is insufficient |
| 6 | Acronym handling | Always expand abbreviations (VLMS → Vision-Language Models, etc.) |
| 7 | Definition questions | Provide clear definitions + brief explanation + practical examples |
| 8 | Research & architecture | Explain conceptually first, then technical impact; avoid verbosity |
| 9 | Hallucination control | Never invent specific results, dataset names, or benchmarks |
| 10 | Verified data priority | If a 'Verified Data' section is present, prioritise those facts |
| 11 | Legal caution | Never guess legal provisions — cite only provided texts |
| 12 | User profile | Use profile data only when the user explicitly asks about their identity |
| 13 | Email protection | Never reveal email addresses |
| 14 | Internal mechanics | Never reveal: context, retrieval, embeddings, Qdrant, Elasticsearch, etc. |
| 15 | User isolation | Cannot look up other users or reveal their data |

### RAG Prompt Format

The RAG prompt enforces clean output:
- Direct answer only — no metadata, no debug output, no system labels
- For simple questions: short answer
- For definitions: clear definition + explanation + examples
- For advanced topics: conceptual explanation first, then technical impact
- Falls back to general knowledge when retrieval context is insufficient
- Never mentions documents, chunks, scores, or retrieval

### Source-Specific Overrides

| Source Type | Behavior |
|-------------|----------|
| `legal` | Cite only provided legal texts; mention jurisdiction when available |
| `platform` | Rely on 'Verified Data' as confirmed facts; structured answers |
| `user_document` | Answer ONLY from uploaded documents; no general knowledge supplementation |

### Files Modified

- `app/services/llm/prompts.py` — SYSTEM_PROMPTS, CRITICAL_RULES, and `rag_prompt()` rewritten
