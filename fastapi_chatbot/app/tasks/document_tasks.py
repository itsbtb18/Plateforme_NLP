"""
Document processing tasks — chunking + embedding user uploads.
"""

import logging
from app.celery_app import celery

logger = logging.getLogger(__name__)


def _make_celery_session():
    """Create a fresh async engine+session for use inside a Celery task
    (the module-level engine is bound to FastAPI's event loop)."""
    from sqlalchemy.ext.asyncio import (
        create_async_engine,
        AsyncSession,
        async_sessionmaker,
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
def process_document(self, document_id: int):
    """Chunk a user-uploaded document and generate embeddings."""
    import asyncio

    asyncio.run(_process_document_async(document_id))


async def _process_document_async(document_id: int):
    from app.models import UserDocument, DocumentChunk
    from app.services.documents.processor import get_document_processor
    from app.services.documents.embeddings import get_embedding_service
    from app.services.documents.entities import extract_entities
    from app.services.language import LanguageService
    from app.services.qdrant import get_qdrant_service, COLLECTION_DOCUMENT_CHUNKS
    from qdrant_client.models import PointStruct
    from sqlalchemy import select

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
                                "source": "user_upload",
                                "entities": chunk_entities,
                            },
                        )
                    )

                # Upsert to Qdrant FIRST so chunks are searchable
                # before the status poller sees "completed"
                qdrant.upsert_batch(COLLECTION_DOCUMENT_CHUNKS, qdrant_points)

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
                doc.status = "failed"
                doc.error_message = str(exc)[:500]
                await db.commit()
                logger.error("Document %d processing failed: %s", document_id, exc)
                raise
    finally:
        await engine.dispose()
