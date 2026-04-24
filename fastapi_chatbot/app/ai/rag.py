from __future__ import annotations

from typing import Any

from qdrant_client.models import Distance, PointStruct, VectorParams

from app.ai.cache import get_ai_cache
from app.config import get_settings
from app.services.documents.embeddings import get_embedding_service
from app.services.qdrant import get_qdrant_service

settings = get_settings()


class AIRagService:
    COLLECTION = "ai_corpus_chunks"

    def __init__(self) -> None:
        self.embeddings = get_embedding_service()
        self.qdrant = get_qdrant_service()
        self.cache = get_ai_cache()
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        client = self.qdrant.client
        names = [c.name for c in client.get_collections().collections]
        if self.COLLECTION not in names:
            client.create_collection(
                collection_name=self.COLLECTION,
                vectors_config=VectorParams(size=settings.EMBEDDING_DIMENSION, distance=Distance.COSINE),
            )

    def upsert_chunks(self, job_id: str, chunks: list[dict[str, Any]]) -> None:
        points: list[PointStruct] = []
        for idx, chunk in enumerate(chunks):
            cache_key = self.cache.stable_hash({"task": "embedding", "text": chunk["text"]})
            cached = self.cache.get_json("embedding", cache_key)
            if cached and isinstance(cached.get("vector"), list):
                vec = cached["vector"]
            else:
                vec = self.embeddings.encode_single(chunk["text"])
                self.cache.set_json(
                    "embedding",
                    cache_key,
                    {"vector": vec},
                    ttl=settings.AI_EMBEDDINGS_CACHE_TTL_SECONDS,
                )
            points.append(
                PointStruct(
                    id=abs(hash(f"{job_id}:{idx}")) % (10**9),
                    vector=vec,
                    payload={
                        "job_id": job_id,
                        "chunk_id": chunk["chunk_id"],
                        "section": chunk.get("section"),
                        "text": chunk["text"][:4000],
                    },
                )
            )
        if points:
            self.qdrant.upsert_batch(self.COLLECTION, points)

    def retrieve(self, query: str, limit: int = 6) -> list[str]:
        cache_key = self.cache.stable_hash({"task": "embedding", "query": query})
        cached = self.cache.get_json("embedding", cache_key)
        if cached and isinstance(cached.get("vector"), list):
            query_vec = cached["vector"]
        else:
            query_vec = self.embeddings.encode_single(query)
            self.cache.set_json(
                "embedding",
                cache_key,
                {"vector": query_vec},
                ttl=settings.AI_EMBEDDINGS_CACHE_TTL_SECONDS,
            )
        hits = self.qdrant.search(self.COLLECTION, query_vec, limit=limit, score_threshold=0.2)
        return [h.get("payload", {}).get("text", "") for h in hits if h.get("payload", {}).get("text")]


_rag: AIRagService | None = None


def get_rag_service() -> AIRagService:
    global _rag
    if _rag is None:
        _rag = AIRagService()
    return _rag
