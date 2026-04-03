"""
NLP research document ingestion — v2 (CPU-safe, resume-safe).

Ingests PDFs (via Docling) and XMLs (via JATS parser) from the data/
directory into PostgreSQL (NLPKnowledge) + Qdrant (nlp_knowledge).

Key features:
  - Resume-safe: checkpoint file tracks completed documents
  - Single-document-at-a-time processing (CPU friendly)
  - Small embedding batch size (8) to limit memory
  - Section filtering (no references, bibliography, appendix)
  - v2 metadata fields: source_file, section_title, document_type, version

Usage::

    # Full ingestion (resumes from checkpoint)
    python -m app.ingestion.ingest_nlp_resources

    # Single file
    python -m app.ingestion.ingest_nlp_resources --file "data/BERT.pdf"

    # Force restart (ignore checkpoint)
    python -m app.ingestion.ingest_nlp_resources --force

    # Dry run (parse only, no DB writes)
    python -m app.ingestion.ingest_nlp_resources --dry-run
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.db import AsyncSessionLocal
from app.models import NLPKnowledge
from app.services.documents.embeddings import get_embedding_service
from app.services.documents.entities import extract_entities
from app.services.qdrant import get_qdrant_service, COLLECTION_NLP_KNOWLEDGE
from app.ingestion.pdf_loader import load_and_chunk_pdf, extract_keywords
from app.ingestion.xml_loader import load_and_chunk_xml
from qdrant_client.models import PointStruct
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = Path(__file__).parent.parent.parent / "data"
EMBEDDING_BATCH_SIZE = 8


def _resolve_checkpoint_file() -> Path:
        """Return a writable checkpoint path.

        Priority:
            1) NLP_INGEST_CHECKPOINT env override
            2) project root checkpoint (when writable)
            3) /tmp fallback inside container/host
        """
        env_path = os.getenv("NLP_INGEST_CHECKPOINT")
        if env_path:
                return Path(env_path)
        return Path(__file__).parent.parent.parent / ".nlp_ingest_checkpoint.json"


CHECKPOINT_FILE = _resolve_checkpoint_file()
FALLBACK_CHECKPOINT_FILE = Path("/tmp/.nlp_ingest_checkpoint.json")

# Document type classification based on filename heuristics
_DOC_TYPE_HINTS = {
    "survey": "survey",
    "review": "survey",
    "comprehensive review": "survey",
    "landscape": "survey",
    "evaluating": "survey",
    "benchmark": "survey",
    "speech and language processing": "book",
    "jurafsky": "book",
    "tutorial": "tutorial",
    "guide": "tutorial",
}


def _classify_doc_type(filename: str) -> str:
    """Guess document type from filename."""
    fn = filename.lower()
    for hint, dtype in _DOC_TYPE_HINTS.items():
        if hint in fn:
            return dtype
    return "paper"


def _detect_file_kind(file_path: Path) -> str | None:
    """Detect ingestible file kind from extension or file header.

    Returns one of: "pdf", "xml", or None for unsupported files.
    """
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".xml":
        return "xml"

    try:
        with open(file_path, "rb") as handle:
            head = handle.read(1024)
    except OSError:
        return None

    if head.startswith(b"%PDF"):
        return "pdf"

    try:
        text_head = head.decode("utf-8", errors="ignore").lstrip()
    except Exception:
        text_head = ""
    if text_head.startswith("<?xml") or "<article" in text_head[:300].lower():
        return "xml"

    return None


# ------------------------------------------------------------------
# Checkpoint management
# ------------------------------------------------------------------

def _load_checkpoint() -> dict:
    for path in (CHECKPOINT_FILE, FALLBACK_CHECKPOINT_FILE):
        if path.exists():
            return json.loads(path.read_text())
    return {"completed_files": [], "failed_files": [], "total_chunks": 0}


def _save_checkpoint(state: dict):
    payload = json.dumps(state, indent=2)
    try:
        CHECKPOINT_FILE.write_text(payload)
    except PermissionError:
        logger.warning(
            "Checkpoint path not writable (%s); using fallback %s",
            CHECKPOINT_FILE,
            FALLBACK_CHECKPOINT_FILE,
        )
        FALLBACK_CHECKPOINT_FILE.write_text(payload)


def _clear_checkpoint():
    for path in (CHECKPOINT_FILE, FALLBACK_CHECKPOINT_FILE):
        if path.exists():
            path.unlink()


# ------------------------------------------------------------------
# Single document ingestion
# ------------------------------------------------------------------

async def ingest_single_document(
    file_path: Path,
    difficulty: str = "intermediate",
    dry_run: bool = False,
) -> int:
    """Ingest one PDF or XML into PostgreSQL + Qdrant.

    Returns the number of chunks ingested.
    """
    file_kind = _detect_file_kind(file_path)

    if file_kind == "pdf":
        parsed = load_and_chunk_pdf(file_path, max_tokens=1000, overlap_tokens=100)
    elif file_kind == "xml":
        parsed = load_and_chunk_xml(file_path, max_tokens=1000, overlap_tokens=100)
    else:
        logger.warning("Unsupported file type: %s — skipping", file_path.name)
        return 0

    title = parsed["title"]
    language = parsed["language"]
    chunks = parsed["chunks"]
    doc_type = _classify_doc_type(file_path.name)

    if not chunks:
        logger.warning("No chunks from %s — skipping", file_path.name)
        return 0

    logger.info(
        "Parsed '%s': %d chunks, type=%s, lang=%s",
        title, len(chunks), doc_type, language,
    )

    if dry_run:
        for c in chunks:
            logger.info(
                "  [DRY] chunk %d: heading=%s, tokens~%d",
                c["index"], c.get("heading", "—")[:50], c["token_est"],
            )
        return len(chunks)

    embedding_service = get_embedding_service()
    qdrant = get_qdrant_service()
    qdrant.ensure_collections()

    async with AsyncSessionLocal() as db:
        points: list[PointStruct] = []
        count = 0

        # Process in small batches to limit memory
        for batch_start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
            batch = chunks[batch_start:batch_start + EMBEDDING_BATCH_SIZE]
            batch_texts = []
            batch_meta = []

            for chunk in batch:
                section_title = chunk["heading"] or f"{title} — chunk {chunk['index']}"
                content = chunk["content"]
                keywords = extract_keywords(content)
                entities = extract_entities(content)

                text_for_embedding = f"{section_title}\n{content}"
                batch_texts.append(text_for_embedding)
                batch_meta.append({
                    "section_title": section_title,
                    "content": content,
                    "keywords": keywords,
                    "entities": entities,
                    "chunk_index": chunk["index"],
                })

            # Batch encode embeddings
            embeddings = embedding_service.encode(batch_texts, batch_size=EMBEDDING_BATCH_SIZE)
            embeddings = [e.tolist() for e in embeddings]

            for i, meta in enumerate(batch_meta):
                entry = NLPKnowledge(
                    topic=meta["section_title"],
                    language=language,
                    content=meta["content"],
                    keywords=meta["keywords"],
                    difficulty=difficulty,
                    source_file=file_path.name,
                    section_title=meta["section_title"],
                    document_type=doc_type,
                    chunk_index=meta["chunk_index"],
                    version=2,
                )
                db.add(entry)
                await db.flush()

                points.append(
                    PointStruct(
                        id=entry.id,
                        vector=embeddings[i],
                        payload={
                            "type": "nlp_knowledge",
                            "language": language,
                            "difficulty": difficulty,
                            "source_file": file_path.name,
                            "document_type": doc_type,
                            "section_title": meta["section_title"],
                            "chunk_index": meta["chunk_index"],
                            "entities": meta["entities"],
                            "version": 2,
                        },
                    )
                )
                count += 1

            logger.info(
                "  Embedded batch %d–%d / %d",
                batch_start + 1,
                min(batch_start + EMBEDDING_BATCH_SIZE, len(chunks)),
                len(chunks),
            )

        await db.commit()
        qdrant.upsert_batch(COLLECTION_NLP_KNOWLEDGE, points, batch_size=32)
        logger.info("Committed %d chunks from '%s'", count, title)
        return count


# ------------------------------------------------------------------
# Batch ingestion with checkpointing
# ------------------------------------------------------------------

async def ingest_all_nlp_docs(
    data_dir: Path,
    difficulty: str = "intermediate",
    force: bool = False,
    dry_run: bool = False,
):
    """Ingest all PDFs and XMLs in data_dir with resume support."""
    all_files = [f for f in data_dir.rglob("*") if f.is_file()]
    files = sorted(
        [f for f in all_files if _detect_file_kind(f) in ("pdf", "xml")],
        key=lambda f: f.stat().st_size,  # smallest first (faster progress)
    )

    if not files:
        logger.warning("No PDF/XML files in %s", data_dir)
        return

    # Load or reset checkpoint
    if force:
        _clear_checkpoint()
        state = {"completed_files": [], "failed_files": [], "total_chunks": 0}
    else:
        state = _load_checkpoint()
        if "failed_files" not in state:
            state["failed_files"] = []

    def _file_key(path: Path) -> str:
        try:
            return str(path.relative_to(data_dir))
        except ValueError:
            return path.name

    completed = set(state["completed_files"])
    completed_basenames = {Path(name).name for name in completed}
    pending = [
        f
        for f in files
        if _file_key(f) not in completed and Path(_file_key(f)).name not in completed_basenames
    ]

    logger.info(
        "Found %d files (%d already completed, %d pending)",
        len(files), len(completed), len(pending),
    )

    for i, file_path in enumerate(pending, 1):
        logger.info(
            "=== [%d/%d] Processing: %s (%.1f MB) ===",
            i, len(pending), file_path.name, file_path.stat().st_size / 1e6,
        )

        try:
            n = await ingest_single_document(file_path, difficulty, dry_run)
            key = _file_key(file_path)
            if key not in completed:
                state["completed_files"].append(key)
                completed.add(key)
                completed_basenames.add(Path(key).name)
            state["total_chunks"] += n
            if not dry_run:
                _save_checkpoint(state)
            logger.info(
                "Checkpoint saved: %d/%d files done, %d total chunks",
                len(state["completed_files"]), len(files), state["total_chunks"],
            )
        except Exception as e:
            logger.error("FAILED on %s: %s", file_path.name, e, exc_info=True)
            key = _file_key(file_path)
            if key not in state["failed_files"]:
                state["failed_files"].append(key)
            if not dry_run:
                _save_checkpoint(state)
            logger.info("Continuing with remaining files...")

    logger.info(
        "Done — %d files processed, %d total chunks ingested",
        len(state["completed_files"]), state["total_chunks"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NLP document ingestion v2")
    parser.add_argument(
        "--dir", type=Path, default=DEFAULT_DATA_DIR,
        help="Directory containing PDF/XML files",
    )
    parser.add_argument(
        "--difficulty", default="intermediate",
        choices=["beginner", "intermediate", "advanced"],
    )
    parser.add_argument(
        "--file", type=Path, default=None,
        help="Single file to ingest",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Ignore checkpoint, restart from scratch",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse and chunk but don't write to DB",
    )
    args = parser.parse_args()

    if args.file:
        asyncio.run(ingest_single_document(args.file, args.difficulty, args.dry_run))
    else:
        asyncio.run(ingest_all_nlp_docs(args.dir, args.difficulty, args.force, args.dry_run))

