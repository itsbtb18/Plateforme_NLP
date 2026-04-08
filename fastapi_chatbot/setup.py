"""
Setup script – initialise database and ingest all knowledge bases.
"""

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

import logging

from app.db import init_db
from app.ingestion.ingest_legal_docs import ingest_legal_documents
from app.ingestion.ingest_nlp_knowledge import ingest_nlp_knowledge
from app.ingestion.ingest_platform_docs import ingest_platform_docs
from app.ingestion.ingest_resources import ingest_resources

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def setup():
    logger.info("Starting FastAPI Chatbot Setup...")

    logger.info("Step 1: Initialising database...")
    await init_db()

    logger.info("Step 2: Ingesting platform documentation...")
    await ingest_platform_docs()

    logger.info("Step 3: Ingesting NLP knowledge base...")
    await ingest_nlp_knowledge()

    logger.info("Step 4: Ingesting research resources...")
    await ingest_resources()

    logger.info("Step 5: Ingesting legal / regulatory documents...")
    await ingest_legal_documents()

    logger.info("Setup completed successfully!")
    logger.info(
        "Start the service: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    )
    logger.info(
        "Start the worker:  celery -A app.celery_app:celery worker -Q chatbot,documents,ingestion -l info"
    )


if __name__ == "__main__":
    asyncio.run(setup())
