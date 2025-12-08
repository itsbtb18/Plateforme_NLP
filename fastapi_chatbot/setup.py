"""
Setup script to initialize the FastAPI chatbot service
"""
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from app.db import init_db
from app.ingestion.ingest_platform_docs import ingest_platform_docs
from app.ingestion.ingest_nlp_knowledge import ingest_nlp_knowledge
from app.ingestion.ingest_resources import ingest_resources
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def setup():
    """Complete setup: initialize database and ingest all data"""
    
    logger.info("🚀 Starting FastAPI Chatbot Setup...")
    
    # Step 1: Initialize database
    logger.info("\n📊 Step 1: Initializing database...")
    await init_db()
    logger.info("✅ Database initialized")
    
    # Step 2: Ingest platform documentation
    logger.info("\n📚 Step 2: Ingesting platform documentation...")
    await ingest_platform_docs()
    logger.info("✅ Platform docs ingested")
    
    # Step 3: Ingest NLP knowledge
    logger.info("\n🧠 Step 3: Ingesting NLP knowledge base...")
    await ingest_nlp_knowledge()
    logger.info("✅ NLP knowledge ingested")
    
    # Step 4: Ingest resources
    logger.info("\n🔬 Step 4: Ingesting research resources...")
    await ingest_resources()
    logger.info("✅ Resources ingested")
    
    logger.info("\n🎉 Setup completed successfully!")
    logger.info("\n🚀 You can now start the service:")
    logger.info("   uvicorn app.main:app --reload --host 0.0.0.0 --port 8001")

if __name__ == "__main__":
    asyncio.run(setup())
