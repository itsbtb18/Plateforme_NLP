"""Qdrant sub-package — vector database access layer."""

from app.services.qdrant.client import QdrantService, get_qdrant_service
from app.services.qdrant.collections import (
    COLLECTION_PLATFORM_DOCS,
    COLLECTION_NLP_KNOWLEDGE,
    COLLECTION_RESOURCES,
    COLLECTION_LEGAL_DOCUMENTS,
    COLLECTION_DOCUMENT_CHUNKS,
    ALL_COLLECTIONS,
)

__all__ = [
    "QdrantService",
    "get_qdrant_service",
    "COLLECTION_PLATFORM_DOCS",
    "COLLECTION_NLP_KNOWLEDGE",
    "COLLECTION_RESOURCES",
    "COLLECTION_LEGAL_DOCUMENTS",
    "COLLECTION_DOCUMENT_CHUNKS",
    "ALL_COLLECTIONS",
]
