"""
Database initialization script for FastAPI chatbot
Run this script to set up the database with pgvector extension and create all tables
"""

import asyncio
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db import init_db, engine
from app.config import get_settings
from sqlalchemy import text
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def initialize_database():
    """Initialize database with pgvector and create all tables"""
    settings = get_settings()
    
    logger.info("=" * 60)
    logger.info("FastAPI Chatbot Database Initialization")
    logger.info("=" * 60)
    logger.info(f"Database URL: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'configured'}")
    logger.info("")
    
    try:
        logger.info("Step 1: Testing database connection...")
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            logger.info(f"✓ Connected to PostgreSQL")
            if version:
                logger.info(f"  Version: {version[:50]}...")
            else:
                logger.info("  Version: Unknown")
        
        logger.info("")
        logger.info("Step 2: Creating pgvector extension...")
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("✓ pgvector extension created/verified")
        
        logger.info("")
        logger.info("Step 3: Creating database tables...")
        await init_db()
        logger.info("✓ All tables created successfully")
        
        logger.info("")
        logger.info("Step 4: Verifying tables...")
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]
            
            if tables:
                logger.info(f"✓ Found {len(tables)} tables:")
                for table in tables:
                    logger.info(f"  - {table}")
            else:
                logger.warning("⚠ No tables found - this might be an issue")
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("✓ Database initialization completed successfully!")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Run the ingestion scripts to populate data:")
        logger.info("   python -m app.ingestion.ingest_nlp_knowledge")
        logger.info("   python -m app.ingestion.ingest_platform_docs")
        logger.info("   python -m app.ingestion.ingest_resources")
        logger.info("")
        logger.info("2. Start the FastAPI server:")
        logger.info("   uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload")
        logger.info("")
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error("❌ Database initialization failed!")
        logger.error("=" * 60)
        logger.error(f"Error: {str(e)}")
        logger.error("")
        logger.error("Troubleshooting:")
        logger.error("1. Check if DATABASE_URL in .env is correct")
        logger.error("2. Ensure PostgreSQL server is running")
        logger.error("3. Verify network connectivity to database")
        logger.error("4. Check if database user has sufficient permissions")
        logger.error("")
        raise
    
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(initialize_database())
