"""
Unified Folder Ingestion Script — Phase 8 extension (PC-safe).

Recursively scans a directory for PDF files, extracts text,
chunks them (with legal-aware logic if specified), and
indexes them into PostgreSQL + Qdrant using the BGE-M3 model.

PC-safe features:
  - Tiny embedding batch size (2) to prevent RAM/CPU spikes
  - asyncio.sleep() pauses between batches to cool CPU
  - Proper language detection via langdetect
  - Per-file error handling so one failure doesn't abort everything

Usage (inside container):
    python app/ingestion/ingest_folder.py --folder /app/data/nlp\ ai\ data\ / --type nlp
    python app/ingestion/ingest_folder.py --folder /app/data/legal\ data/ --type law
"""

import asyncio
import argparse
import gc
import logging
import sys
from pathlib import Path
from typing import List, Dict

# Add app root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from langdetect import detect
from app.db import AsyncSessionLocal
from app.models import NLPKnowledge, LegalDocument
from app.services.documents.processor import get_document_processor
from app.services.documents.embeddings import get_embedding_service
from app.services.qdrant import (
    get_qdrant_service,
    COLLECTION_NLP_KNOWLEDGE,
    COLLECTION_LEGAL_DOCUMENTS,
)
from qdrant_client.models import PointStruct

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingest_folder")

# PC-safe batching settings
EMBED_BATCH_SIZE = 2
UPSERT_BATCH_SIZE = 8
SLEEP_BETWEEN_BATCHES = 1.0  # seconds


def _detect_language(text: str) -> str:
    """Detect language using langdetect — handles French, Arabic, English."""
    try:
        return detect(text[:2000])
    except Exception:
        return "fr"  # default to French for legal docs


def _looks_like_pdf(file_bytes: bytes) -> bool:
    """Detect PDF payload by magic bytes even when file has no extension."""
    return file_bytes.startswith(b"%PDF-")


def _sanitize_text(text: str) -> str:
    """Remove characters rejected by PostgreSQL UTF-8 storage."""
    return text.replace("\x00", " ")


async def process_file(
    file_path: Path, doc_type: str, processor, embedding_service, db, qdrant
):
    """Process a single file and index its chunks (PC-safe batching)."""
    logger.info("📄 Processing: %s", file_path.name)

    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        if file_path.suffix.lower() == ".pdf" or _looks_like_pdf(file_bytes):
            pages = processor.extract_pdf_text(file_bytes)
            full_text = "\n\n".join(p["content"] for p in pages)

            if doc_type == "law":
                chunks = processor.chunk_legal(full_text, page_map=pages)
            else:
                chunks = processor.chunk_text(full_text, page_map=pages)
        else:
            # For .txt or unknown, treat as flat text
            text = file_bytes.decode("utf-8", errors="replace")
            chunks = processor.chunk_text(text)

        if not chunks:
            logger.warning(
                "⚠️ No text extracted from %s, using fallback content", file_path.name
            )
            fallback_text = _sanitize_text(
                file_bytes.decode("utf-8", errors="ignore")
            ).strip()
            if not fallback_text:
                fallback_text = (
                    f"Document '{file_path.name}' ingested with limited extraction."
                )
            chunks = [{"content": fallback_text}]

        chunk_texts = [
            _sanitize_text(c["content"]).strip()
            for c in chunks
            if _sanitize_text(c["content"]).strip()
        ]
        if not chunk_texts:
            chunk_texts = [
                f"Document '{file_path.name}' ingested with limited extraction."
            ]

        # Detect language from first chunk (reliable for whole-document language)
        file_language = _detect_language(chunk_texts[0])
        logger.info(
            "  Detected language: %s, %d chunks to embed",
            file_language,
            len(chunk_texts),
        )

        # --- PC-safe: embed in tiny batches with sleep ---
        points: List[PointStruct] = []
        collection = (
            COLLECTION_LEGAL_DOCUMENTS
            if doc_type == "law"
            else COLLECTION_NLP_KNOWLEDGE
        )

        for i in range(0, len(chunk_texts), EMBED_BATCH_SIZE):
            batch_texts = chunk_texts[i : i + EMBED_BATCH_SIZE]
            batch_chunks = chunks[i : i + EMBED_BATCH_SIZE]
            embeddings = embedding_service.encode(
                batch_texts, batch_size=EMBED_BATCH_SIZE
            )

            for idx_in_batch, (content, embedding) in enumerate(
                zip(batch_texts, embeddings)
            ):
                global_idx = i + idx_in_batch

                if doc_type == "law":
                    doc_entry = LegalDocument(
                        title=f"{file_path.stem} (Part {global_idx + 1})",
                        content=content,
                        category="folder-ingested",
                        jurisdiction="Algeria",
                        language=file_language,
                        source_reference=file_path.name,
                    )
                    payload = {
                        "type": "law",
                        "language": file_language,
                        "title": f"{file_path.stem} (Part {global_idx + 1})",
                        "content": content[:500],  # truncated for BM25
                        "source": file_path.name,
                        "chunk_index": global_idx,
                        "article_heading": batch_chunks[idx_in_batch].get(
                            "article_heading"
                        ),
                    }
                else:
                    doc_entry = NLPKnowledge(
                        topic=f"{file_path.stem} (Part {global_idx + 1})",
                        content=content,
                        language=file_language,
                        difficulty="advanced",
                    )
                    payload = {
                        "type": "nlp_knowledge",
                        "language": file_language,
                        "content": content[:500],  # truncated for BM25
                        "source": file_path.name,
                        "chunk_index": global_idx,
                    }

                db.add(doc_entry)
                await db.flush()  # Get the ID

                points.append(
                    PointStruct(
                        id=doc_entry.id,
                        vector=embedding.tolist()
                        if hasattr(embedding, "tolist")
                        else embedding,
                        payload=payload,
                    )
                )

            # Upsert in small batches to avoid memory buildup
            if len(points) >= UPSERT_BATCH_SIZE:
                qdrant.upsert_batch(collection, points, batch_size=UPSERT_BATCH_SIZE)
                points = []

            logger.info(
                "  Embedded %d/%d chunks",
                min(i + EMBED_BATCH_SIZE, len(chunk_texts)),
                len(chunk_texts),
            )
            await asyncio.sleep(SLEEP_BETWEEN_BATCHES)  # Cool down CPU

        # Flush remaining points
        if points:
            qdrant.upsert_batch(collection, points, batch_size=UPSERT_BATCH_SIZE)

        await db.commit()
        logger.info(
            "✅ Indexed %d chunks from %s [lang=%s]",
            len(chunk_texts),
            file_path.name,
            file_language,
        )

        # Free memory
        gc.collect()

    except Exception as e:
        logger.error(
            "❌ Failed to process %s: %s", file_path.name, str(e), exc_info=True
        )
        await db.rollback()


async def main():
    parser = argparse.ArgumentParser(description="Ingest a folder of documents.")
    parser.add_argument(
        "--folder", type=str, required=True, help="Path to folder to scan"
    )
    parser.add_argument(
        "--type",
        type=str,
        choices=["nlp", "law"],
        default="nlp",
        help="Type of knowledge",
    )
    args = parser.parse_args()

    folder_path = Path(args.folder)
    if not folder_path.exists() or not folder_path.is_dir():
        logger.error("Folder not found: %s", args.folder)
        return

    processor = get_document_processor()
    embedding_service = get_embedding_service()
    qdrant = get_qdrant_service()

    # Include all files. PDF payloads are detected by signature even without extension.
    files = [p for p in folder_path.rglob("*") if p.is_file()]

    logger.info("🚀 Found %d files in %s. Type: %s", len(files), folder_path, args.type)

    async with AsyncSessionLocal() as db:
        for file_idx, file_path in enumerate(files):
            logger.info("--- File %d/%d ---", file_idx + 1, len(files))
            await process_file(
                file_path, args.type, processor, embedding_service, db, qdrant
            )
            await asyncio.sleep(2.0)  # Extra cool-down between files

    logger.info("🎉 Ingestion complete!")


if __name__ == "__main__":
    asyncio.run(main())
