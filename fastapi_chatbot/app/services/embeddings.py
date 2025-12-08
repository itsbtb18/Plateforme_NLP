from sentence_transformers import SentenceTransformer
from app.config import get_settings
import logging
import numpy as np
from typing import List, Union

logger = logging.getLogger(__name__)
settings = get_settings()

class EmbeddingService:
    """Service for generating embeddings using sentence-transformers"""
    
    def __init__(self):
        self.model_name = settings.EMBEDDING_MODEL
        logger.info(f"Loading embedding model: {self.model_name}")
        
        try:
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"✅ Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load embedding model: {str(e)}")
            raise
    
    def encode(self, texts: Union[str, List[str]], batch_size: int = 32) -> np.ndarray:
        """
        Generate embeddings for text(s)
        
        Args:
            texts: Single text or list of texts
            batch_size: Batch size for processing
            
        Returns:
            numpy array of embeddings
        """
        try:
            if isinstance(texts, str):
                texts = [texts]
            
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            
            return embeddings
        
        except Exception as e:
            logger.error(f"❌ Embedding generation failed: {str(e)}")
            raise
    
    def encode_single(self, text: str) -> List[float]:
        """Generate embedding for a single text and return as list"""
        embedding = self.encode(text)
        return embedding[0].tolist()
    
    def get_dimension(self) -> int:
        """Get embedding dimension"""
        dimension = self.model.get_sentence_embedding_dimension()
        if dimension is None:
            raise ValueError("Unable to determine embedding dimension")
        return dimension

# Singleton instance
_embedding_service = None

def get_embedding_service() -> EmbeddingService:
    """Get or create embedding service instance"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
