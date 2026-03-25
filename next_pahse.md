# Next Phase Prompt (Claude) — Classifier + Memory Intelligence + Evaluation Upgrade

You are a senior AI engineer specialized in production RAG systems, multilingual intent routing, and LLM evaluation.
Your task is to implement a **new upgrade phase** on top of an existing chatbot architecture.

This phase focuses on:
1. classifier improvements,
2. memory-aware conversational commands,
3. robust multilingual behavior (Arabic/French/English),
4. evaluation metrics (Precision@k, Recall@k, MRR, BERTScore).

You must preserve existing architecture and extend it safely.

## Non-Negotiable Rules

1. Do NOT remove existing pipeline components.
2. Do NOT break existing Django modes/endpoints.
3. Do NOT bypass existing classify -> route -> retrieve -> generate -> verify flow.
4. All additions must be backward-compatible.
5. Implement as modular upgrade, not rewrite.

---

## Existing System (Must Be Preserved)

### Current architecture summary
- Query rewrite -> intent classification -> query router -> retrieval (hybrid for RAG paths) -> context builder -> LLM generation -> faithfulness verification -> persistence.
- Existing intent families include platform/user/legal/document/conceptual/general paths.
- Existing session memory persists chat history and supports token-budgeted retrieval of recent messages.

### Existing bridge and routes
- Django `mode` handling is already implemented and must remain valid.
- Existing FastAPI endpoints for conversation/platform/legal/document flows must stay functional.

---

## Upgrade Goal A — Classifier Intelligence for Memory Commands

Add a classifier extension for **conversation-memory intents** (meta-queries about prior turns), without breaking current intents.

### New memory-aware intents to add
- `memory_translate_last_user_query`
- `memory_repeat_last_user_query`
- `memory_summarize_last_answer`
- `memory_compare_last_two_queries`

### Multilingual detection requirements
The classifier must detect these intents in Arabic, French, and English forms, for example:
- Arabic: "ترجم آخر سؤال إلى الإنجليزية"
- French: "traduis ma dernière question en anglais"
- English: "translate my last query to english"

### Important routing rule
These memory intents should be handled before heavy retrieval.
If a memory intent is detected, do not run full RAG retrieval unless needed.

### Ambiguity behavior
If classifier confidence is low between memory intent and normal intent:
- use lightweight LLM disambiguation,
- log decision path,
- keep safe fallback to existing behavior.

---

## Upgrade Goal B — Memory Model and Retrieval of Prior Turns

Implement memory utilities so the assistant can operate on prior user turns safely.

### Required capabilities
1. Fetch the last user query in the session.
2. Fetch the last assistant answer in the session.
3. Fetch the last two user queries for comparison intent.
4. Exclude system/internal messages from memory-command operations.

### Required behavior example
If user asks in Arabic:
- Turn N: user asks Arabic question.
- Turn N+1: "translate last query to english"
System must return the English translation of the **last user query**, not the last assistant answer.

### Memory safety and quality
- If there is no prior message, return explicit graceful response.
- Add guardrails to avoid leaking unrelated session content.
- Keep token-efficient operations for memory intents.

### Data model constraints
- Reuse current session/message tables where possible.
- Add minimal metadata fields only if necessary.
- Do not introduce breaking schema changes.

---

## Upgrade Goal C — Translation and Language-Aware Memory Responses

For memory translation intents:
- detect target language from user command,
- if target language omitted, default to English,
- provide literal-preserving translation for legal/technical queries,
- avoid rewriting meaning.

Add structured helper functions:
- `extract_memory_intent(question, language)`
- `get_last_user_query(session_id)`
- `translate_text(text, target_lang)`
- `handle_memory_intent(intent, session_id, question)`

---

## Upgrade Goal D — Evaluation Framework (from report requirements)

Implement or update an evaluation module to measure chatbot quality using:
- Precision@k
- Recall@k
- MRR
- BERTScore

### Evaluation scope
1. Retrieval evaluation:
- Precision@k, Recall@k, MRR using labeled relevance (qrels-style data).

2. Generation evaluation:
- BERTScore between reference answers and model answers.

### Reproducibility requirements
- fixed test dataset,
- deterministic evaluation configuration,
- clear script output and saved report artifacts.

### Reporting requirements
Output per-run report with:
- aggregate metrics,
- per-query metrics,
- failure cases (low recall / low BERTScore),
- configuration used (top_k, reranker on/off, language).

---

## Integration Requirements

### Classifier integration points
- Extend existing classifier engine, do not replace core intent taxonomy.
- Add mapping layer so new memory intents route cleanly.

### Memory integration points
- Extend session service with explicit methods for "last user query" and related history helpers.
- Keep compatibility with existing message persistence APIs.

### Router/chat logic integration
- Add early branch for memory intents in chat orchestration.
- Return source label indicating memory operation (for observability).

### Logging / observability
Log structured fields:
- detected_intent,
- intent_confidence,
- memory_action,
- memory_hit/miss,
- translation_target_lang,
- evaluation_mode (if running benchmark).

---

## Tests (Mandatory)

Add tests for:

1. Classifier memory intents
- AR/FR/EN examples recognized correctly.

2. Memory behavior
- last user query retrieval,
- correct handling when history is empty,
- translation of last query (Arabic to English scenario).

3. Regression tests
- existing legal/platform/document/general routes still work.

4. Evaluation tests
- metric functions compute expected values on synthetic mini dataset.

---

## Deliverables Required from Claude

Provide:
1. exact file changes,
2. modular code implementation,
3. migration notes (if schema changed),
4. test execution results,
5. evaluation script usage example,
6. known risks and follow-up recommendations.

---

## Hard Constraints Recap

- Extend architecture, do not rewrite it.
- Preserve existing routing and retrieval behavior.
- Add memory-aware multilingual classifier features.
- Support commands like translating the previous user query to English.
- Implement evaluation metrics: Precision@k, Recall@k, MRR, BERTScore.
- Keep production-safe, testable, and observable code.
