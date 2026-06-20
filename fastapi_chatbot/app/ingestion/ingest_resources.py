"""
Ingestion script for research resource PDFs.

Uses Docling to parse PDF files, chunks them intelligently,
and persists structured data in PostgreSQL + embeddings in Qdrant.

Usage::

    # Ingest all PDFs in data/
    python -m app.ingestion.ingest_resources

    # Ingest a single PDF
    python -m app.ingestion.ingest_resources --file data/AraBERT.pdf

    # With metadata overrides
    python -m app.ingestion.ingest_resources --file data/AraBERT.pdf \\
        --type article --author "Wissam Antoun" --year 2020

    # From a different directory
    python -m app.ingestion.ingest_resources --dir data/resources/
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from app.db import AsyncSessionLocal
from app.models import Resource
from app.services.documents.embeddings import get_embedding_service
from app.services.documents.entities import extract_entities
from app.services.qdrant import get_qdrant_service, COLLECTION_RESOURCES
from app.ingestion.pdf_loader import load_and_chunk_pdf, extract_keywords
from qdrant_client.models import PointStruct
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = Path(__file__).parent.parent.parent / "data"


async def ingest_resource_pdf(
    pdf_path: Path,
    resource_type: str = "article",
    author: str | None = None,
    institution: str | None = None,
    year: int | None = None,
    url: str | None = None,
    country: str | None = None,
):
    """Ingest a single research-resource PDF into PostgreSQL + Qdrant.

    Each chunk of the document becomes a separate ``Resource`` row and
    a corresponding Qdrant point in the ``resources`` collection.
    """
    embedding_service = get_embedding_service()
    qdrant = get_qdrant_service()
    qdrant.ensure_collections()

    parsed = load_and_chunk_pdf(pdf_path, max_tokens=1000, overlap_tokens=100)
    title = parsed["title"]
    language = parsed["language"]
    chunks = parsed["chunks"]

    if not chunks:
        logger.warning("No chunks extracted from %s — skipping", pdf_path.name)
        return 0

    async with AsyncSessionLocal() as db:
        logger.info("Ingesting resource '%s' — %d chunks", title, len(chunks))
        points: list[PointStruct] = []
        count = 0

        for chunk in chunks:
            chunk_title = chunk["heading"] or f"{title} — part {chunk['index']}"
            content = chunk["content"]
            tags = extract_keywords(content)
            entities = extract_entities(content)

            text_for_embedding = f"{chunk_title}\n{content}"
            embedding = embedding_service.encode_single(text_for_embedding)

            res = Resource(
                type=resource_type,
                title=chunk_title,
                url=url,
                description=content,
                tags=tags,
                country=country,
                author=author,
                institution=institution,
                year=year,
            )
            db.add(res)
            await db.flush()

            points.append(
                PointStruct(
                    id=res.id,
                    vector=embedding,
                    payload={
                        "type": resource_type,
                        "language": language,
                        "country": country or "",
                        "city": "",
                        "source_file": pdf_path.name,
                        "chunk_index": chunk["index"],
                        "entities": entities,
                    },
                )
            )
            count += 1
            logger.info(
                "  [%d/%d] title=%s  tokens~%d  id=%d",
                chunk["index"] + 1,
                len(chunks),
                chunk_title[:60],
                chunk["token_est"],
                res.id,
            )

        await db.commit()
        qdrant.upsert_batch(COLLECTION_RESOURCES, points)
        logger.info("Ingested %d chunks from '%s'", count, title)
        return count


async def ingest_all_resource_pdfs(
    data_dir: Path,
    resource_type: str = "article",
):
    """Ingest every PDF found in *data_dir* as a research resource."""
    pdf_files = sorted(data_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning("No PDF files found in %s", data_dir)
        return

    logger.info("Found %d PDF files in %s", len(pdf_files), data_dir)
    total = 0
    for pdf in pdf_files:
        n = await ingest_resource_pdf(pdf, resource_type=resource_type)
        total += n
    logger.info(
        "Done — ingested %d total chunks from %d PDFs", total, len(pdf_files)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest research resource PDFs")
    parser.add_argument(
        "--dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing PDF files (default: data/)",
    )
    parser.add_argument(
        "--type",
        default="article",
        choices=["article", "dataset", "project", "tutorial", "book"],
        help="Resource type for all entries (default: article)",
    )
    parser.add_argument("--author", default=None, help="Author name")
    parser.add_argument("--institution", default=None, help="Institution name")
    parser.add_argument("--year", type=int, default=None, help="Publication year")
    parser.add_argument("--url", default=None, help="Source URL or DOI")
    parser.add_argument("--country", default=None, help="Country of origin")
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Single PDF file to ingest (overrides --dir)",
    )
    args = parser.parse_args()

    if args.file:
        asyncio.run(
            ingest_resource_pdf(
                args.file,
                resource_type=args.type,
                author=args.author,
                institution=args.institution,
                year=args.year,
                url=args.url,
                country=args.country,
            )
        )
    else:
        asyncio.run(
            ingest_all_resource_pdfs(args.dir, resource_type=args.type)
        )
