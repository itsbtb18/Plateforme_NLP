"""
Ingestion tasks — legal documents + web page crawling.
"""
import logging
from app.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, name="app.tasks.ingest_legal_batch", max_retries=1)
def ingest_legal_batch(self, documents: list):
    """Ingest a batch of legal documents with embeddings into PG + Qdrant."""
    import asyncio
    asyncio.run(_ingest_legal_async(documents))


async def _ingest_legal_async(documents: list):
    from app.db import AsyncSessionLocal
    from app.models import LegalDocument
    from app.services.documents.embeddings import get_embedding_service
    from app.services.qdrant import get_qdrant_service, COLLECTION_LEGAL_DOCUMENTS
    from qdrant_client.models import PointStruct

    embedding_service = get_embedding_service()
    qdrant = get_qdrant_service()

    async with AsyncSessionLocal() as db:
        points: list[PointStruct] = []
        for doc_data in documents:
            text = f"{doc_data['title']} {doc_data['content']}"
            emb = embedding_service.encode_single(text)
            legal_doc = LegalDocument(
                title=doc_data["title"],
                jurisdiction=doc_data.get("jurisdiction"),
                category=doc_data.get("category"),
                content=doc_data["content"],
                language=doc_data.get("language", "en"),
                source_reference=doc_data.get("source_reference"),
                keywords=doc_data.get("keywords"),
            )
            db.add(legal_doc)
            await db.flush()

            points.append(
                PointStruct(
                    id=legal_doc.id,
                    vector=emb,
                    payload={
                        "type": "law",
                        "language": legal_doc.language or "en",
                        "jurisdiction": legal_doc.jurisdiction or "",
                        "category": legal_doc.category or "",
                    },
                )
            )

        await db.commit()
        qdrant.upsert_batch(COLLECTION_LEGAL_DOCUMENTS, points)
        logger.info("Ingested %d legal documents via Celery", len(documents))


@celery.task(bind=True, name="app.tasks.crawl_and_index_url", max_retries=2)
def crawl_and_index_url(self, url: str, collection: str = "platform_docs"):
    """Crawl a web page, extract text, chunk, embed, and store in Qdrant."""
    import asyncio
    asyncio.run(_crawl_and_index_async(url, collection))


async def _crawl_and_index_async(url: str, collection: str):
    from app.db import AsyncSessionLocal
    from app.models import PlatformDoc
    from app.services.documents.processor import get_document_processor
    from app.services.documents.embeddings import get_embedding_service
    from app.services.qdrant import get_qdrant_service
    from qdrant_client.models import PointStruct
    import urllib.request
    import html
    import re

    processor = get_document_processor()
    embedding_service = get_embedding_service()
    qdrant = get_qdrant_service()

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NLPBot/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw_html = resp.read().decode("utf-8", errors="replace")

        # Simple HTML → text (strip tags)
        text = re.sub(r"<[^>]+>", " ", raw_html)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) < 50:
            logger.warning("Too little text from %s", url)
            return

        title = url.split("/")[-1] or url

        chunks = processor.chunk_text(text)
        embeddings = embedding_service.encode(
            [c["content"] for c in chunks], batch_size=32,
        )

        async with AsyncSessionLocal() as db:
            doc = PlatformDoc(
                title=title, slug=url, content=text[:5000], category="web",
            )
            db.add(doc)
            await db.flush()

            points = [
                PointStruct(
                    id=doc.id * 10000 + idx,
                    vector=emb.tolist(),
                    payload={
                        "type": "nlp_knowledge",
                        "language": "en",
                        "source_url": url,
                        "chunk_index": idx,
                    },
                )
                for idx, emb in enumerate(embeddings)
            ]
            await db.commit()
            qdrant.upsert_batch(collection, points)

        logger.info("Crawled & indexed %s — %d chunks", url, len(chunks))

    except Exception as exc:
        logger.error("Crawl failed for %s: %s", url, exc)
        raise
