"""
Qdrant vector database service.

Manages collections and provides insert / search operations.
All embedding columns have been removed from PostgreSQL;
Qdrant is the single source of truth for vector data.
"""
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchParams,
)
from app.config import get_settings
from app.services.qdrant.collections import ALL_COLLECTIONS
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


class QdrantService:
    """Thin wrapper around the Qdrant client."""

    def __init__(self):
        self.client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            grpc_port=settings.QDRANT_GRPC_PORT,
            api_key=settings.QDRANT_API_KEY or None,
            prefer_grpc=settings.QDRANT_PREFER_GRPC,
        )
        self.dimension = settings.EMBEDDING_DIMENSION
        logger.info(
            "Qdrant client initialised (%s:%s)", settings.QDRANT_HOST, settings.QDRANT_PORT,
        )

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def recreate_collections(self) -> None:
        """Delete and recreate all collections. Used for model upgrades."""
        for name in ALL_COLLECTIONS:
            try:
                self.client.delete_collection(collection_name=name)
                logger.info("Deleted Qdrant collection: %s", name)
            except Exception:
                logger.debug("Collection %s did not exist for deletion", name)

            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=self.dimension,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Recreated Qdrant collection: %s (dim=%d)", name, self.dimension)

    def ensure_collections(self) -> None:
        """Create collections if they do not exist."""
        existing = [c.name for c in self.client.get_collections().collections]
        for name in ALL_COLLECTIONS:
            if name not in existing:
                self.client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=self.dimension,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info("Created missing Qdrant collection: %s", name)
            else:
                logger.debug("Qdrant collection exists: %s", name)

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def upsert(
        self,
        collection: str,
        point_id: int,
        vector: List[float],
        payload: Optional[Dict] = None,
    ) -> None:
        """Upsert a single point."""
        self.client.upsert(
            collection_name=collection,
            points=[
                PointStruct(id=point_id, vector=vector, payload=payload or {}),
            ],
        )

    def upsert_batch(
        self,
        collection: str,
        points: List[PointStruct],
        batch_size: int = 64,
    ) -> None:
        """Upsert points in batches."""
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(collection_name=collection, points=batch)
        logger.info("Upserted %d points into %s", len(points), collection)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        collection: str,
        query_vector: List[float],
        limit: int = 5,
        score_threshold: Optional[float] = None,
        query_filter: Optional[Filter] = None,
    ) -> List[Dict]:
        """Search a collection and return results as dicts.

        Each dict contains:
          - id (int)
          - score (float)  — cosine similarity
          - payload (dict)
        """
        threshold = (
            score_threshold if score_threshold is not None else settings.SIMILARITY_THRESHOLD
        )
        results = self.client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=limit,
            score_threshold=threshold,
            query_filter=query_filter,
            search_params=SearchParams(exact=False, hnsw_ef=128),
        )
        hits = [
            {"id": hit.id, "score": hit.score, "payload": hit.payload or {}}
            for hit in results
        ]
        logger.debug(
            "Qdrant search: collection=%s limit=%d threshold=%.2f → %d hits",
            collection, limit, threshold, len(hits),
        )
        return hits

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_by_filter(self, collection: str, key: str, value) -> None:
        """Delete points matching a payload filter."""
        self.client.delete(
            collection_name=collection,
            points_selector=Filter(
                must=[FieldCondition(key=key, match=MatchValue(value=value))],
            ),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_qdrant_service: Optional[QdrantService] = None


def get_qdrant_service() -> QdrantService:
    global _qdrant_service
    if _qdrant_service is None:
        _qdrant_service = QdrantService()
    return _qdrant_service
