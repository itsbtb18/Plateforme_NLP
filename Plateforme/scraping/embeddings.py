"""
Semantic embedding utilities for duplicate detection.

Uses ``paraphrase-multilingual-MiniLM-L12-v2`` (384-dim) to generate
title embeddings stored in pgvector for cosine-similarity lookups.
"""

from sentence_transformers import SentenceTransformer
import numpy as np
from django.conf import settings

_model = None


def get_embedding_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(
            'paraphrase-multilingual-MiniLM-L12-v2'
        )
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
    from scraping.models import ScrapedItemMeta
    from pgvector.django import CosineDistance

    new_embedding = get_embedding(new_title)
    if new_embedding is None:
        return False

    similar = ScrapedItemMeta.objects.filter(
        category=category,
        title_embedding__isnull=False
    ).annotate(
        distance=CosineDistance('title_embedding', new_embedding)
    ).filter(
        distance__lt=(1 - threshold)
    ).exists()

    return similar
