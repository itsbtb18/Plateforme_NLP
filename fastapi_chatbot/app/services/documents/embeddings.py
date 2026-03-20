"""
Embedding service — multilingual sentence-transformer model.

Phase 6: the model MUST be multilingual so that Arabic, French, and
English texts share a single vector space.  Cross-language retrieval
is supported natively — no per-language index is needed.
"""
from sentence_transformers import SentenceTransformer
from app.config import get_settings
import logging
import numpy as np
from typing import List, Union

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingService:
    """Generate dense vector embeddings for text."""

    _MULTILINGUAL_MODELS = {
        "BAAI/bge-m3",
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "sentence-transformers/distiluse-base-multilingual-cased-v2",
    }

    def __init__(self):
        self.model_name = settings.EMBEDDING_MODEL
        logger.info("Loading embedding model: %s", self.model_name)

        if self.model_name not in self._MULTILINGUAL_MODELS:
            logger.warning(
                "Embedding model '%s' is not in the verified multilingual list. "
                "Cross-language retrieval may not work correctly.",
                self.model_name,
            )

        try:
            self.model = SentenceTransformer(self.model_name)
            logger.info("Multilingual embedding model loaded successfully")
        except Exception as e:
            logger.error("Failed to load embedding model: %s", e)
            raise

    def encode(self, texts: Union[str, List[str]], batch_size: int = 32) -> np.ndarray:
        """Generate embeddings for text(s).

        Returns numpy array of shape (n, dim).
        """
        if isinstance(texts, str):
            texts = [texts]
        return self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

    def encode_single(self, text: str) -> List[float]:
        """Generate embedding for a single text and return as list."""
        return self.encode(text)[0].tolist()

    def get_dimension(self) -> int:
        """Get embedding dimension."""
        dimension = self.model.get_sentence_embedding_dimension()
        if dimension is None:
            raise ValueError("Unable to determine embedding dimension")
        return dimension


# Singleton
_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
