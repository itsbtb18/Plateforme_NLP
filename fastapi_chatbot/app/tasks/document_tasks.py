"""
Document processing tasks — chunking + embedding user uploads.
"""

import json
import logging
import os
from datetime import UTC, datetime

from app.celery_app import celery

logger = logging.getLogger(__name__)

ES_INDEX_DOCUMENT_CHUNKS = "document_chunks"
HYBRID_DEAD_LETTER_FILE = os.getenv(
    "HYBRID_STORE_DEAD_LETTER_FILE",
    "logs/hybrid_store_dead_letters.jsonl",
)


def _record_hybrid_dead_letter(payload: dict) -> None:
    try:
        os.makedirs(os.path.dirname(HYBRID_DEAD_LETTER_FILE), exist_ok=True)
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            **payload,
        }
        with open(HYBRID_DEAD_LETTER_FILE, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.error("hybrid_dead_letter_write_failed: %s", exc)


def _es_indexing_enabled() -> bool:
    return os.getenv("HYBRID_STORE_ES_INDEXING", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def _index_chunks_in_es(es_documents: list[dict]) -> None:
    if not es_documents:
        return

    from app.config import get_settings
    from elasticsearch import AsyncElasticsearch

    settings = get_settings()
    client = AsyncElasticsearch(hosts=[settings.ELASTICSEARCH_HOST], request_timeout=15)
    try:
        for doc in es_documents:
            await client.index(
                index=ES_INDEX_DOCUMENT_CHUNKS, id=str(doc["id"]), document=doc
            )
    finally:
        await client.close()


async def _delete_chunks_from_es(doc_ids: list[int]) -> None:
    if not doc_ids:
        return

    from app.config import get_settings
    from elasticsearch import AsyncElasticsearch

    settings = get_settings()
    client = AsyncElasticsearch(hosts=[settings.ELASTICSEARCH_HOST], request_timeout=10)
    try:
        for doc_id in doc_ids:
            try:
                await client.delete(
                    index=ES_INDEX_DOCUMENT_CHUNKS, id=str(doc_id), ignore=[404]
                )
            except Exception:
                continue
    finally:
        await client.close()


def _delete_points_from_qdrant(
    qdrant, collection_name: str, point_ids: list[int]
) -> None:
    if not point_ids:
        return
    try:
        qdrant.client.delete(collection_name=collection_name, points_selector=point_ids)
    except Exception as exc:
        logger.warning("qdrant_compensation_delete_failed: %s", exc)


def _make_celery_session():
    """Create a fresh async engine+session for use inside a Celery task
    (the module-level engine is bound to FastAPI's event loop)."""
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from app.config import get_settings

    settings = get_settings()
    eng = create_async_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=3,
        pool_recycle=300,
        connect_args={
            "server_settings": {"application_name": "celery_worker"},
            "command_timeout": 120,
            "timeout": 30,
        },
    )
    factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    return eng, factory


@celery.task(bind=True, name="app.tasks.process_document", max_retries=2)
def process_document(self, document_id: int, source: str = "user_upload"):
    """Chunk a user-uploaded document and generate embeddings."""
    import asyncio

    asyncio.run(_process_document_async(document_id, source=source))


async def _process_document_async(document_id: int, source: str = "user_upload"):
    from qdrant_client.models import PointStruct
    from sqlalchemy import select

    from app.models import DocumentChunk, UserDocument
    from app.services.documents.embeddings import get_embedding_service
    from app.services.documents.entities import extract_entities
    from app.services.documents.processor import get_document_processor
    from app.services.language import LanguageService
    from app.services.qdrant import COLLECTION_DOCUMENT_CHUNKS, get_qdrant_service

    processor = get_document_processor()
    embedding_service = get_embedding_service()
    lang_service = LanguageService()
    qdrant = get_qdrant_service()

    engine, SessionLocal = _make_celery_session()
    try:
        async with SessionLocal() as db:
            stmt = select(UserDocument).where(UserDocument.id == document_id)
            result = await db.execute(stmt)
            doc = result.scalar_one_or_none()

            if not doc:
                logger.error("Document %d not found", document_id)
                return

            try:
                doc.status = "processing"
                await db.commit()

                raw_text = doc.raw_text
                if not raw_text:
                    raise ValueError("No text content available for chunking")

                cleaned = processor.clean_text(raw_text)
                doc_language = lang_service.detect(cleaned[:2000])
                chunks = processor.chunk_text(cleaned)

                # Generate embeddings in batches
                batch_size = 32
                all_embeddings = []
                for i in range(0, len(chunks), batch_size):
                    batch_texts = [c["content"] for c in chunks[i : i + batch_size]]
                    batch_emb = embedding_service.encode(
                        batch_texts, batch_size=batch_size
                    )
                    all_embeddings.extend(batch_emb.tolist())

                # Persist chunk text in PostgreSQL, embeddings in Qdrant
                qdrant_points: list[PointStruct] = []
                point_ids: list[int] = []
                es_documents: list[dict] = []
                for idx, (chunk, emb) in enumerate(zip(chunks, all_embeddings)):
                    db_chunk = DocumentChunk(
                        document_id=document_id,
                        chunk_index=idx,
                        content=chunk["content"],
                        page_number=chunk.get("page"),
                    )
                    db.add(db_chunk)
                    await db.flush()

                    # Phase 10: extract named entities for search boosting
                    chunk_entities = extract_entities(chunk["content"])

                    qdrant_points.append(
                        PointStruct(
                            id=db_chunk.id,
                            vector=emb,
                            payload={
                                "type": "document",
                                "language": doc_language,
                                "owner_id": doc.user_id or "",
                                "document_id": document_id,
                                "session_id": doc.session_id,
                                "filename": doc.filename,
                                "chunk_index": idx,
                                "source": source,
                                "entities": chunk_entities,
                            },
                        )
                    )
                    point_ids.append(db_chunk.id)
                    es_documents.append(
                        {
                            "id": db_chunk.id,
                            "document_id": document_id,
                            "owner_id": doc.user_id or "",
                            "session_id": doc.session_id,
                            "filename": doc.filename,
                            "chunk_index": idx,
                            "language": doc_language,
                            "type": "document",
                            "source": source,
                            "content": chunk["content"][:4000],
                        }
                    )

                # Upsert to Qdrant FIRST so chunks are searchable
                # before the status poller sees "completed"
                qdrant_upserted = False
                es_indexed = False

                qdrant.upsert_batch(COLLECTION_DOCUMENT_CHUNKS, qdrant_points)
                qdrant_upserted = True

                if _es_indexing_enabled():
                    await _index_chunks_in_es(es_documents)
                    es_indexed = True

                doc.total_chunks = len(chunks)
                doc.status = "completed"
                await db.commit()
                logger.info(
                    "Document %d processed: %d chunks, lang=%s",
                    document_id,
                    len(chunks),
                    doc_language,
                )

            except Exception as exc:
                await db.rollback()

                if "qdrant_upserted" in locals() and qdrant_upserted:
                    _delete_points_from_qdrant(
                        qdrant,
                        COLLECTION_DOCUMENT_CHUNKS,
                        point_ids,
                    )

                if "es_indexed" in locals() and es_indexed:
                    await _delete_chunks_from_es(point_ids)

                _record_hybrid_dead_letter(
                    {
                        "category": "document_chunks",
                        "document_id": document_id,
                        "collection": COLLECTION_DOCUMENT_CHUNKS,
                        "index": ES_INDEX_DOCUMENT_CHUNKS,
                        "point_ids": point_ids,
                        "error": str(exc),
                    }
                )

                doc.status = "failed"
                doc.error_message = str(exc)[:500]
                await db.commit()
                logger.error("Document %d processing failed: %s", document_id, exc)
                raise
    finally:
        await engine.dispose()
