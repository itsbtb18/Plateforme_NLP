"""
Database initialization script for FastAPI chatbot.

Creates PostgreSQL tables and Qdrant vector collections.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.db import init_db, engine
from app.config import get_settings
from sqlalchemy import text
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def initialize_database():
    """Initialize PostgreSQL tables and Qdrant collections."""
    settings = get_settings()

    logger.info("=" * 60)
    logger.info("FastAPI Chatbot Database Initialization")
    logger.info("=" * 60)
    logger.info(
        "Database URL: %s",
        settings.DATABASE_URL.split("@")[1] if "@" in settings.DATABASE_URL else "configured",
    )
    logger.info("")

    try:
        # --- PostgreSQL ---
        logger.info("Step 1: Testing PostgreSQL connection...")
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            logger.info("  Connected to PostgreSQL")
            if version:
                logger.info("  Version: %s...", str(version)[:50])

        logger.info("")
        logger.info("Step 2: Creating PostgreSQL tables...")
        await init_db()
        logger.info("  All tables created successfully")

        logger.info("")
        logger.info("Step 3: Verifying tables...")
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
                    "ORDER BY table_name"
                )
            )
            tables = [row[0] for row in result]
            if tables:
                logger.info("  Found %d tables:", len(tables))
                for table in tables:
                    logger.info("    - %s", table)

        # --- Qdrant ---
        logger.info("")
        logger.info("Step 4: Initialising Qdrant collections...")
        from app.services.qdrant import get_qdrant_service

        qdrant = get_qdrant_service()
        qdrant.ensure_collections()
        logger.info("  Qdrant collections ready")

        logger.info("")
        logger.info("=" * 60)
        logger.info("Database initialization completed successfully!")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Run the ingestion scripts to populate data:")
        logger.info("   python -m app.ingestion.ingest_nlp_knowledge")
        logger.info("   python -m app.ingestion.ingest_platform_docs")
        logger.info("   python -m app.ingestion.ingest_resources")
        logger.info("   python -m app.ingestion.ingest_legal_docs")
        logger.info("")
        logger.info("2. Start the FastAPI server:")
        logger.info("   uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload")
        logger.info("")

    except Exception as e:
        logger.error("=" * 60)
        logger.error("Database initialization failed!")
        logger.error("=" * 60)
        logger.error("Error: %s", e)
        logger.error("")
        logger.error("Troubleshooting:")
        logger.error("1. Check DATABASE_URL in .env")
        logger.error("2. Ensure PostgreSQL is running")
        logger.error("3. Ensure Qdrant is running (port %d)", settings.QDRANT_PORT)
        logger.error("4. Verify network connectivity")
        raise


if __name__ == "__main__":
    asyncio.run(initialize_database())
