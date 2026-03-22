# After Phase - Session Change Log (Before vs After)

This document summarizes what was done across the recent debugging and stabilization session, what the system behavior was before, what was changed, and what it looks like now.

## 1) Initial Problems Observed (Before)

### Runtime and routing issues
- Django stream endpoint was returning 500.
- FastAPI service had startup/availability instability in Docker.
- Port conflict on host made FastAPI unavailable on expected host port.

### Retrieval and data issues
- Legal retrieval worked in some paths, but NLP/conceptual retrieval was inconsistent.
- Database and vector index coverage were not aligned (especially NLP and legal point counts over time).
- Some conceptual queries answered without retrieved context.

### Response quality issues
- Frequent fallback answers after first successful response.
- Fallback reason was mostly provider rate-limit pressure (HTTP 429), not only routing.
- A legal safety fallback message was appearing for non-legal questions in some cases.

### UX and intent issues
- Pasted mixed content (analysis text + platform words like "author", "open") could be misrouted toward platform intent in some classifier paths.
- This could lead to odd response shape and confusing user experience.

### Latency issues
- Requests could take very long due to stacked retry behavior.
- Baseline measured examples before optimization:
  - hello: ~61.98s
  - what is rag: ~80.88s
  - arabic legal question: ~210.99s

## 2) What Was Changed

### A) Critical bug fix in Django stream path
- File: `Plateforme/chatbot/views.py`
- Fix: removed variable shadowing that broke translation call in stream endpoint.
- Result: stream endpoint no longer crashes with that TypeError path.

### B) Docker/runtime stabilization
- File: `docker-compose.yml`
- Change: FastAPI host port mapping moved from 8000 to 8001 to avoid host conflict.
- Result: service reachable consistently from host side on mapped port.

### C) FastAPI startup behavior
- File: `fastapi_chatbot/app/main.py`
- Change: heavy warmup tasks moved to background startup path.
- Result: reduced startup blocking and better service availability.

### D) LLM resilience under rate limits
- File: `fastapi_chatbot/app/services/llm/client.py`
- Added:
  - retry/backoff handling for normal and streaming paths
  - alternate internal key/model failover after primary exhaustion
- Result: reduced hard failures under 429 storms and improved completion continuity.

### E) Faithfulness fallback scope fix
- File: `fastapi_chatbot/app/services/chat_logic.py`
- Change: legal-safe fallback substitution now enforced only for legal answers.
- Result: non-legal NLP/conceptual questions no longer collapse into legal fallback text.

### F) Misrouting fix for pasted-answer analysis prompts
- File: `fastapi_chatbot/app/services/classifier/engine.py`
- Added correction heuristic for long pasted analysis prompts containing platform-like UI words.
- Result: these prompts are forced to conceptual intent instead of accidental platform intent.

### G) Index coverage and reindex operations
- Executed:
  - NLP reindex completed (161/161)
  - Legal reindex completed (358 records processed)
- Observed final structure:
  - legal DB records: 358
  - legal vector points: 395 (expected due multi-chunk docs)
  - distinct legal doc IDs in vectors: 358
- Result: DB and vector coverage aligned logically.

### H) Latency optimization (fail-fast strategy)
- File: `fastapi_chatbot/app/services/llm/client.py`
- Changes:
  - disabled SDK-level auto retries (`max_retries=0`)
  - reduced request timeout for provider calls
  - reduced app-level retries and delay
- Result: substantially faster responses in normal operation.

## 3) Before vs After Summary

| Area | Before | After |
|---|---|---|
| Django stream endpoint | Could 500 due runtime bug | Stable for that bug path |
| FastAPI host access | Port conflict / instability | Reachable via host mapping (8001 -> 8000) |
| Rate-limit behavior | Frequent hard fallback loops | Retry + failover path implemented |
| Legal fallback application | Could appear for non-legal flows | Limited to legal intent/source branch |
| Pasted mixed analysis query routing | Could drift to platform intent | Corrected toward conceptual intent |
| NLP index completeness | Incomplete / partial runs | Reindex completed (161/161) |
| Legal index completeness | In progress / mismatched counts | Reindex complete; multi-chunk structure validated |
| Latency | Often very high under retries | Reduced significantly with fail-fast tuning |

## 4) Measured Performance Notes

### Earlier baseline (pre-latency tuning)
- hello: ~61.98s
- what is rag: ~80.88s
- arabic legal query: ~210.99s

### Post-tuning sample benchmark (same environment session)
- hello: ~1.64s
- what is rag: ~5.10s
- arabic legal query: ~8.43s

Note: timings can still vary with provider load and rate-limit windows, but the worst-case wait profile was reduced by removing stacked retry layers.

## 5) Data and Retrieval Status Now

- Legal corpus ingestion coverage is present in DB (358 rows) and represented in vectors with chunk-level expansion.
- NLP knowledge is indexed to vector store (161 rows / points).
- Cross-language legal retrieval capability was validated at retrieval layer during session checks.
- Platform card overexposure for pasted analysis prompts was reduced by intent correction logic.

## 6) Remaining Risks / Follow-up

- Provider 429 pressure can still degrade answer quality; now it fails faster instead of waiting very long.
- Some queries can still return generic fallback under sustained provider throttling.
- Optional next improvement: add short TTL cache for frequent simple prompts and classifier outputs to further smooth latency under load.

## 7) Files Updated in This Session (Core)

- `Plateforme/chatbot/views.py`
- `docker-compose.yml`
- `fastapi_chatbot/app/main.py`
- `fastapi_chatbot/app/services/llm/client.py`
- `fastapi_chatbot/app/services/chat_logic.py`
- `fastapi_chatbot/app/services/classifier/engine.py`

## 8) Temporary/Support Scripts Added During Debugging

- `fastapi_chatbot/tmp_crosslang_test.py`
- `fastapi_chatbot/tmp_nlp_retrieval_test.py`
- `fastapi_chatbot/tmp_seed_rag.py`
- `reports/tmp_retrieval_test.py`

These were used for validation and targeted diagnostics.
