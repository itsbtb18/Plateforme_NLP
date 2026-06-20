"""
Maintenance tasks — re-indexing Qdrant collections.
"""
import logging
from app.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, name="app.tasks.reindex_collection", max_retries=1)
def reindex_collection(self, collection_name: str):
    """Re-embed and re-index all records for a Qdrant collection."""
    import asyncio
    asyncio.run(_reindex_collection_async(collection_name))


async def _reindex_collection_async(collection_name: str):
    from app.db import AsyncSessionLocal
    from app.models import PlatformDoc, NLPKnowledge, Resource, LegalDocument
    from app.services.documents.embeddings import get_embedding_service
    from app.services.qdrant import (
        get_qdrant_service,
        COLLECTION_PLATFORM_DOCS,
        COLLECTION_NLP_KNOWLEDGE,
        COLLECTION_RESOURCES,
        COLLECTION_LEGAL_DOCUMENTS,
    )
    from qdrant_client.models import PointStruct
    from sqlalchemy import select

    model_map = {
        COLLECTION_PLATFORM_DOCS: PlatformDoc,
        COLLECTION_NLP_KNOWLEDGE: NLPKnowledge,
        COLLECTION_RESOURCES: Resource,
        COLLECTION_LEGAL_DOCUMENTS: LegalDocument,
    }

    model_cls = model_map.get(collection_name)
    if not model_cls:
        logger.error("Unknown collection for reindex: %s", collection_name)
        return

    embedding_service = get_embedding_service()
    qdrant = get_qdrant_service()

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(model_cls))).scalars().all()

    if not rows:
        logger.info("No rows to reindex for %s", collection_name)
        return

    batch_size = 64
    all_points: list[PointStruct] = []

    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        texts = [f"{r.title} {r.content}"[:1000] for r in batch]
        embeddings = embedding_service.encode(texts, batch_size=batch_size)

        for row, emb in zip(batch, embeddings):
            payload = {"title": row.title[:200]}
            type_map = {
                COLLECTION_PLATFORM_DOCS: "nlp_knowledge",
                COLLECTION_NLP_KNOWLEDGE: "nlp_knowledge",
                COLLECTION_RESOURCES: getattr(row, "type", "article"),
                COLLECTION_LEGAL_DOCUMENTS: "law",
            }
            payload["type"] = type_map.get(collection_name, "nlp_knowledge")
            payload["language"] = getattr(row, "language", None) or "en"
            if hasattr(row, "category"):
                payload["category"] = row.category or ""
            all_points.append(
                PointStruct(id=row.id, vector=emb.tolist(), payload=payload)
            )

    # Recreate collection with fresh data
    qdrant.ensure_collections()
    qdrant.upsert_batch(collection_name, all_points)
    logger.info("Re-indexed %s: %d records", collection_name, len(all_points))
