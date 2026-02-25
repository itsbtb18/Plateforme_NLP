"""
app.services.retrieval — vector retrieval pipeline.

Public API:
  - hybrid_search          (cross-collection orchestrator)
  - search_platform_docs   (platform docs collection)
  - search_nlp_knowledge   (NLP knowledge collection)
  - search_resources       (resources collection)
  - search_legal_documents (legal documents collection)
  - search_user_documents  (user uploaded chunks collection)
  - deduplicate            (content deduplication)
  - rerank                 (cosine re-scoring)
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

__all__ = [
    "hybrid_search",
    "search_platform_docs",
    "search_nlp_knowledge",
    "search_resources",
    "search_legal_documents",
    "search_user_documents",
    "deduplicate",
    "rerank",
]
