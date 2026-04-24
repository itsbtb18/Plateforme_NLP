"""
Safely clean only NLP index data (PostgreSQL + Qdrant).

Legal, platform, and document indices are never touched.

Usage::

    # Preview what will be deleted (dry run)
    python -m app.ingestion.cleanup_nlp --dry-run

    # Delete all NLP data (seed + PDF chunks)
    python -m app.ingestion.cleanup_nlp --all

    # Delete only PDF-ingested chunks (keep seed rows 1-14)
    python -m app.ingestion.cleanup_nlp --pdf-only

    # Reset auto-increment sequence after cleanup
    python -m app.ingestion.cleanup_nlp --all --reset-sequence
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import delete, func, select, text

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.db import AsyncSessionLocal
from app.models import NLPKnowledge
from app.services.qdrant import COLLECTION_NLP_KNOWLEDGE, get_qdrant_service

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

SEED_MAX_ID = 14  # Original hand-written seed rows


async def cleanup_nlp(
    mode: str = "all",
    dry_run: bool = False,
    reset_sequence: bool = False,
):
    """Delete NLP data from PostgreSQL and Qdrant.

    Modes:
        all      — delete everything in nlp_knowledge
        pdf-only — delete only rows with id > SEED_MAX_ID (keep seeds)
    """
    qdrant = get_qdrant_service()

    async with AsyncSessionLocal() as db:
        # Count current state
        total = (await db.execute(select(func.count(NLPKnowledge.id)))).scalar() or 0
        seed_count = (
            await db.execute(
                select(func.count(NLPKnowledge.id)).where(
                    NLPKnowledge.id <= SEED_MAX_ID
                )
            )
        ).scalar() or 0
        pdf_count = total - seed_count

        logger.info(
            "Current state: %d total rows (%d seed, %d PDF chunks)",
            total,
            seed_count,
            pdf_count,
        )

        if mode == "all":
            target_count = total
            logger.info("Mode: ALL — will delete %d rows", target_count)
        else:
            target_count = pdf_count
            logger.info(
                "Mode: PDF-ONLY — will delete %d PDF chunk rows (keeping %d seeds)",
                target_count,
                seed_count,
            )

        if dry_run:
            logger.info("DRY RUN — no changes made")
            return

        if target_count == 0:
            logger.info("Nothing to delete")
            return

        # --- PostgreSQL cleanup ---
        if mode == "all":
            await db.execute(delete(NLPKnowledge))
        else:
            await db.execute(delete(NLPKnowledge).where(NLPKnowledge.id > SEED_MAX_ID))
        await db.commit()
        logger.info("PostgreSQL: deleted %d rows", target_count)

        # Reset sequence if requested
        if reset_sequence:
            if mode == "all":
                await db.execute(
                    text("ALTER SEQUENCE nlp_knowledge_id_seq RESTART WITH 1")
                )
            else:
                next_val = SEED_MAX_ID + 1
                await db.execute(
                    text(f"ALTER SEQUENCE nlp_knowledge_id_seq RESTART WITH {next_val}")
                )
            await db.commit()
            logger.info("PostgreSQL: sequence reset")

        # --- Qdrant cleanup ---
        try:
            if mode == "all":
                # Recreate the collection (fastest way to clear all points)
                from qdrant_client.models import Distance, VectorParams

                qdrant.client.delete_collection(COLLECTION_NLP_KNOWLEDGE)
                qdrant.client.create_collection(
                    collection_name=COLLECTION_NLP_KNOWLEDGE,
                    vectors_config=VectorParams(size=768, distance=Distance.COSINE),
                )
                logger.info("Qdrant: recreated %s collection", COLLECTION_NLP_KNOWLEDGE)
            else:
                # Delete only PDF points (id > SEED_MAX_ID)
                # Scroll to get all point IDs, then delete in batches
                all_ids = []
                offset = None
                while True:
                    points, next_offset = qdrant.client.scroll(
                        collection_name=COLLECTION_NLP_KNOWLEDGE,
                        limit=100,
                        offset=offset,
                        with_payload=False,
                        with_vectors=False,
                    )
                    for p in points:
                        if isinstance(p.id, int) and p.id > SEED_MAX_ID:
                            all_ids.append(p.id)
                    if next_offset is None:
                        break
                    offset = next_offset

                if all_ids:
                    from qdrant_client.models import PointIdsList

                    for i in range(0, len(all_ids), 500):
                        batch = all_ids[i : i + 500]
                        qdrant.client.delete(
                            collection_name=COLLECTION_NLP_KNOWLEDGE,
                            points_selector=PointIdsList(points=batch),
                        )
                    logger.info("Qdrant: deleted %d points", len(all_ids))
                else:
                    logger.info("Qdrant: no PDF points to delete")

        except Exception as e:
            logger.error("Qdrant cleanup error: %s", e)

    logger.info("Cleanup complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean NLP index data safely")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Delete all NLP data")
    group.add_argument(
        "--pdf-only", action="store_true", help="Delete only PDF chunks, keep seeds"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview only, no changes"
    )
    parser.add_argument(
        "--reset-sequence", action="store_true", help="Reset PostgreSQL ID sequence"
    )
    args = parser.parse_args()

    mode = "all" if args.all else "pdf-only"
    asyncio.run(
        cleanup_nlp(mode=mode, dry_run=args.dry_run, reset_sequence=args.reset_sequence)
    )
