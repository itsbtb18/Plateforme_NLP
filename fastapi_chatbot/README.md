# NLP Platform Chatbot — Advanced RAG Pipeline

This document outlines the architecture, evolution, and operations of the upgraded NLP Chatbot. The system has transitioned from a basic RAG setup to a multi-phase, production-grade pipeline designed for high accuracy and multilingual support.

## 🚀 The Evolution (Phases 1–8)

The project followed a structured phased upgrade to ensure robustness and performance.

### Before the Upgrade
- **Intent Detection**: Simple Regex and keyword matching (unreliable for complex queries).
- **Retrieval**: Single-collection vector search (could miss context in other tables).
- **Inference**: Direct LLM response without validation (prone to hallucinations).
- **Ingestion**: Basic text extraction without structural awareness.

### After the Upgrade
- **Phase 2: Zero-shot LLM Classifier**: Every query is first analyzed by an LLM to detect intent (legal, bug, conceptual, etc.) with high precision.
- **Phase 3: Intelligent Routing**: Queries are automatically routed to the most relevant data source (Qdrant, PostgreSQL, or Elasticsearch).
- **Phase 4: Hybrid Search & Reranking**: Combines **Dense Vectors (BGE-M3)** and **BM25 Sparse Search** using Reciprocal Rank Fusion (RRF), followed by a semantic reranker.
- **Phase 5: Multi-turn Context**: Queries are rewritten in real-time to include context from previous messages (e.g., "Tell me more" → "Tell me more about the word embeddings we just discussed").
- **Phase 6: Faithfulness Verification**: A secondary LLM process checks if the generated answer is actually supported by the retrieved context before showing it to the user.
- **Phase 7: Structural Ingestion (Docling)**: Uses the **Docling** library to understand PDF structure (headings, sections), ensuring chunks are semantically complete.
- **Phase 8: Master Re-indexing**: Fully upgraded all collections to the **BGE-M3 (1024d)** embedding model for superior multilingual RAG.

---

## 🏗️ Architecture

1.  **Query Rewriter**: Contextualizes the user's question.
2.  **Intent Classifier**: Detects the "Goal" of the user (e.g., `legal_query`).
3.  **Search Router**: Directs the query to the correct Qdrant collections.
4.  **Hybrid Searcher**: Retrieves results using both Vector and Keyword search.
5.  **RRF & Reranker**: Fuses results and re-scores them for maximum relevance.
6.  **Context Builder**: Assembles the "Knowledge" for the LLM.
7.  **Answer Generator**: LLM (Groq/Llama-3) generates a polite, human-like response.
8.  **Faithfulness Guard**: Ensures no hallucinations are delivered.

---

## 📂 Data Ingestion (How to Ingest Code & Data)

To populate the knowledge base or update it after a model change, use the master re-indexing script.

### ⚠️ Safety First (Preventing Overheating)
The embedding process (BGE-M3) is CPU-intensive. To prevent your PC from overheating:
- **Never run more than one** re-indexing process at a time.
- The script includes built-in `asyncio.sleep` to let the CPU cool down.

### Commands

**To re-index everything (Wipe and Start Fresh):**
```bash
docker exec -it 9da1242581f8 python3 -m app.ingestion.reindex_all
```

**To re-index only specific collections (e.g., Legal):**
```bash
docker exec -it 9da1242581f8 python3 -m app.ingestion.reindex_all --only legal
```

**To RESUME re-indexing (Append without wiping):**
```bash
docker exec -it 9da1242581f8 python3 -m app.ingestion.reindex_all --only legal --no-wipe
```

**To run in the background (Safe Mode):**
```bash
docker exec -d 9da1242581f8 python3 -m app.ingestion.reindex_all --only legal --no-wipe
```

---

## 🛠️ Components List
- **Embeddings**: BAAI/bge-m3 (1024 dimensions)
- **Vector DB**: Qdrant
- **Keyword Search**: Elasticsearch / BM25
- **LLM**: Groq (Llama 3.1 8B/70B)
- **PDF Extraction**: Docling (IBM)
- **Framework**: FastAPI (Asynchronous)
