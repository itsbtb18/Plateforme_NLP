"""
Semantic embedding utilities for duplicate detection.

Uses ``paraphrase-multilingual-MiniLM-L12-v2`` (384-dim) to generate
title embeddings stored in pgvector for cosine-similarity lookups.
"""

import logging

from django.db import connection
from sentence_transformers import SentenceTransformer

_model = None
logger = logging.getLogger(__name__)


def get_embedding_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _model


def get_embedding(text):
    """Return a 384-dim normalised embedding list, or ``None`` for short/empty text."""
    if not text or len(text.strip()) < 3:
        return None
    model = get_embedding_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def is_semantic_duplicate(new_title, category, threshold=0.88):
    """Return ``True`` if *new_title* is semantically close to an existing item.

    Uses pgvector's ``CosineDistance`` to find items within the given
    *threshold* (default 0.88 cosine similarity → distance < 0.12).
    """

    return find_semantic_duplicate(new_title, category, threshold=threshold) is not None


def find_semantic_duplicate(new_title, category, threshold=0.88):
    """Return the closest matching ``ScrapedItemMeta`` row when duplicate.

    Returns ``None`` when no semantic duplicate exists above threshold.
    """
    # pgvector operators are PostgreSQL-specific and can raise SQL errors on SQLite.
    if connection.vendor != "postgresql":
        return None

    try:
        from pgvector.django import CosineDistance
    except Exception:
        logger.debug("pgvector_not_available_for_semantic_dedup", exc_info=True)
        return None

    from scraping.models import ScrapedItemMeta

    new_embedding = get_embedding(new_title)
    if new_embedding is None:
        return None

    try:
        return (
            ScrapedItemMeta.objects.filter(
                category=category,
                title_embedding__isnull=False,
            )
            .annotate(distance=CosineDistance("title_embedding", new_embedding))
            .filter(distance__lt=(1 - threshold))
            .order_by("distance")
            .first()
        )
    except Exception:
        logger.debug("semantic_dedup_query_failed", exc_info=True)
        return None
