"""
Master re-indexing script — Phase 8.

Wipes all Qdrant collections and re-ingests all data from PostgreSQL
using the new embedding model (BGE-M3, 1024d) and structure-aware chunking.

Efficiency (PC-safe) features:
  - Batching: encodes text in small groups (def: 2) to limit RAM/CPU spikes.
  - Re-chunking: applies Phase 7 legal-aware chunking to existing legal documents.
  - Progress tracking: logs success/failure per document.
  - CPU Throttle: adds asyncio.sleep to let CPU cool down between heavy embedding batches.
"""

import asyncio
import gc
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from qdrant_client.models import PointStruct

from app.db import AsyncSessionLocal
from app.models import NLPKnowledge, PlatformDoc, Resource, LegalDocument, UserDocument
from app.services.documents.embeddings import get_embedding_service
from app.services.documents.processor import get_document_processor
from app.services.qdrant import get_qdrant_service
from app.services.qdrant.collections import (
    COLLECTION_NLP_KNOWLEDGE,
    COLLECTION_PLATFORM_DOCS,
    COLLECTION_RESOURCES,
    COLLECTION_LEGAL_DOCUMENTS,
    COLLECTION_DOCUMENT_CHUNKS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("reindex_all")

# PC-safe batching settings (lowered to prevent overheating)
EMBED_BATCH_SIZE = 2
UPSERT_BATCH_SIZE = 1  # Set to 1 for immediate visibility/debugging
SLEEP_TIME = 0.5  # seconds to sleep between batches to cool down CPU


async def reindex_nlp_knowledge(db, embedding_service, qdrant):
    logger.info("Re-indexing NLP Knowledge...")
    stmt = select(NLPKnowledge)
    result = await db.execute(stmt)
    records = result.scalars().all()
    
    points = []
    for i in range(0, len(records), EMBED_BATCH_SIZE):
        batch = records[i:i + EMBED_BATCH_SIZE]
        texts = [f"{r.topic}\n{r.content}" for r in batch]
        embeddings = embedding_service.encode(texts, batch_size=EMBED_BATCH_SIZE)
        
        for record, emb in zip(batch, embeddings):
            points.append(
                PointStruct(
                    id=record.id,
                    vector=emb.tolist(),
                    payload={
                        "type": "nlp_knowledge",
                        "language": record.language or "en",
                        "difficulty": record.difficulty or "",
                        "title": record.topic,
                        "content": record.content[:800],
                    },
                )
            )
        logger.info("  Processed %d/%d nlp_knowledge entries", min(i + EMBED_BATCH_SIZE, len(records)), len(records))
        
        if len(points) >= UPSERT_BATCH_SIZE:
            qdrant.upsert_batch(COLLECTION_NLP_KNOWLEDGE, points, batch_size=UPSERT_BATCH_SIZE)
            points = []
            
        await asyncio.sleep(SLEEP_TIME)  # Cool down

    if points:
        qdrant.upsert_batch(COLLECTION_NLP_KNOWLEDGE, points, batch_size=UPSERT_BATCH_SIZE)
    logger.info("  NLP Knowledge: done (%d records)", len(records))
    gc.collect()


async def reindex_platform_docs(db, embedding_service, qdrant):
    logger.info("Re-indexing Platform Docs...")
    stmt = select(PlatformDoc)
    result = await db.execute(stmt)
    records = result.scalars().all()
    
    points = []
    for i in range(0, len(records), EMBED_BATCH_SIZE):
        batch = records[i:i + EMBED_BATCH_SIZE]
        texts = [f"{r.title}\n{r.content}" for r in batch]
        embeddings = embedding_service.encode(texts, batch_size=EMBED_BATCH_SIZE)
        
        for record, emb in zip(batch, embeddings):
            points.append(
                PointStruct(
                    id=record.id,
                    vector=emb.tolist(),
                    payload={
                        "type": "platform_docs",
                        "language": "en",
                        "slug": record.slug,
                        "category": record.category or "",
                        "title": record.title,
                        "content": record.content[:800],
                    },
                )
            )
        logger.info("  Processed %d/%d platform_docs entries", min(i + EMBED_BATCH_SIZE, len(records)), len(records))
        
        if len(points) >= UPSERT_BATCH_SIZE:
            qdrant.upsert_batch(COLLECTION_PLATFORM_DOCS, points, batch_size=UPSERT_BATCH_SIZE)
            points = []
            
        await asyncio.sleep(SLEEP_TIME)  # Cool down

    if points:
        qdrant.upsert_batch(COLLECTION_PLATFORM_DOCS, points, batch_size=UPSERT_BATCH_SIZE)
    logger.info("  Platform Docs: done (%d records)", len(records))
    gc.collect()


async def reindex_legal_docs(db, embedding_service, qdrant, processor):
    logger.info("Re-indexing Legal Documents (with re-chunking)...")
    stmt = select(LegalDocument)
    result = await db.execute(stmt)
    records = result.scalars().all()
    
    points = []
    for record in records:
        logger.info("  -> Processing legal doc: id=%d, title=%s", record.id, record.title[:50])
        # Phase 7: Use legal-aware chunking
        chunks = processor.chunk_legal(record.content)
        if not chunks:
            continue
            
        texts = [c["content"] for c in chunks]
        # Adding title to each chunk for better context
        texts = [f"{record.title}\n{t}" for t in texts]
        
        # Batch chunking within the document to avoid massive RAM/CPU spikes
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            try:
                batch_texts = texts[i:i + EMBED_BATCH_SIZE]
                batch_chunks = chunks[i:i + EMBED_BATCH_SIZE]
                embeddings = embedding_service.encode(batch_texts, batch_size=EMBED_BATCH_SIZE)
                
                for idx, (chunk, emb) in enumerate(zip(batch_chunks, embeddings)):
                    global_idx = i + idx
                    points.append(
                        PointStruct(
                            id=record.id * 1000 + global_idx,
                            vector=emb.tolist(),
                            payload={
                                "doc_id": record.id,
                                "type": "law",
                                "language": record.language or "fr",
                                "jurisdiction": record.jurisdiction or "",
                                "category": record.category or "",
                                "title": record.title,
                                "content": chunk.get("content", "")[:1000],
                                "article_heading": chunk.get("article_heading"),
                            },
                        )
                    )
                await asyncio.sleep(SLEEP_TIME)
            except Exception as e:
                logger.error("  Error embedding chunks for doc %d: %s", record.id, e)
                continue
            
            if len(points) >= UPSERT_BATCH_SIZE:
                qdrant.upsert_batch(COLLECTION_LEGAL_DOCUMENTS, points, batch_size=UPSERT_BATCH_SIZE)
                points = []
                await asyncio.sleep(SLEEP_TIME)
                
        logger.info("  Re-chunked and embedded: %s (id=%d) -> %d chunks", record.title, record.id, len(chunks))

    if points:
        qdrant.upsert_batch(COLLECTION_LEGAL_DOCUMENTS, points, batch_size=UPSERT_BATCH_SIZE)
    logger.info("  Legal Documents: done (%d records)", len(records))
    gc.collect()


async def reindex_resources(db, embedding_service, qdrant):
    logger.info("Re-indexing Resources...")
    stmt = select(Resource)
    result = await db.execute(stmt)
    records = result.scalars().all()
    
    points = []
    for i in range(0, len(records), EMBED_BATCH_SIZE):
        batch = records[i:i + EMBED_BATCH_SIZE]
        texts = [f"{r.title}\n{r.description}" for r in batch]
        embeddings = embedding_service.encode(texts, batch_size=EMBED_BATCH_SIZE)
        
        for record, emb in zip(batch, embeddings):
            points.append(
                PointStruct(
                    id=record.id,
                    vector=emb.tolist(),
                    payload={
                        "type": record.type,
                        "language": "en",
                        "country": record.country or "",
                        "city": record.city or "",
                        "title": record.title,
                        "content": record.description[:800],
                    },
                )
            )
        logger.info("  Processed %d/%d resources", min(i + EMBED_BATCH_SIZE, len(records)), len(records))
        
        if len(points) >= UPSERT_BATCH_SIZE:
            qdrant.upsert_batch(COLLECTION_RESOURCES, points, batch_size=UPSERT_BATCH_SIZE)
            points = []
            
        await asyncio.sleep(SLEEP_TIME)  # Cool down

    if points:
        qdrant.upsert_batch(COLLECTION_RESOURCES, points, batch_size=UPSERT_BATCH_SIZE)
    logger.info("  Resources: done (%d records)", len(records))
    gc.collect()


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=["nlp", "platform", "resources", "legal"], help="Only re-index one collection")
    parser.add_argument("--no-wipe", action="store_true", help="Do not delete collections before re-indexing")
    parser.add_argument("--force", action="store_true", help="Deprecated, use --no-wipe logically") # Keep for compat if needed
    args = parser.parse_args()

    logger.info("🚀 Starting Master Re-indexing (Phase 8 - Ultra Safe Mode)...")
    
    # 1. Initialize services
    embedding_service = get_embedding_service()
    qdrant = get_qdrant_service()
    processor = get_document_processor()
    
    # 2. Recreate collections with new dimensions (if not skipping)
    if not args.no_wipe:
        logger.info("Wiping and recreating Qdrant collections for 1024d...")
        qdrant.recreate_collections()
    else:
        logger.info("Skipping collection wipe, appending/updating points...")
    
    # Let the PC rest before start
    await asyncio.sleep(1.0)
    
    # 3. Process tables
    async with AsyncSessionLocal() as db:
        if not args.only or args.only == "nlp":
            await reindex_nlp_knowledge(db, embedding_service, qdrant)
            await asyncio.sleep(2.0)
        
        if not args.only or args.only == "platform":
            await reindex_platform_docs(db, embedding_service, qdrant)
            await asyncio.sleep(2.0)
            
        if not args.only or args.only == "resources":
            await reindex_resources(db, embedding_service, qdrant)
            await asyncio.sleep(2.0)
            
        if not args.only or args.only == "legal":
            await reindex_legal_docs(db, embedding_service, qdrant, processor)
        
    logger.info("✅ Re-indexing complete!")


if __name__ == "__main__":
    asyncio.run(main())
