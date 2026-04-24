"""
app.services.retrieval — vector retrieval pipeline.

Public API:
  - hybrid_search          (dense + sparse → RRF fusion)
  - search_platform_docs   (platform docs collection)
  - search_nlp_knowledge   (NLP knowledge collection)
  - search_resources       (resources collection)
  - search_legal_documents (legal documents collection)
  - search_user_documents  (user uploaded chunks collection)
  - deduplicate            (content deduplication)
  - rerank                 (cosine re-scoring)
  - search_bm25            (BM25 sparse search, Phase 4)
  - build_index_from_docs  (build BM25 index, Phase 4)
"""
from app.services.retrieval.hybrid import hybrid_search
from app.services.retrieval.search import (
    search_platform_docs,
    search_nlp_knowledge,
    search_resources,
    search_legal_documents,
    search_user_documents,
)
from app.services.retrieval.reranker import deduplicate, rerank
from app.services.retrieval.bm25 import search_bm25, build_index_from_docs

__all__ = [
    "hybrid_search",
    "search_platform_docs",
    "search_nlp_knowledge",
    "search_resources",
    "search_legal_documents",
    "search_user_documents",
    "deduplicate",
    "rerank",
    "search_bm25",
    "build_index_from_docs",
]
