from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from app.config import get_settings
from typing import AsyncGenerator
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Create async engine with better connection handling
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    connect_args={
        "server_settings": {"application_name": "fastapi_chatbot"},
        "command_timeout": 60,
        "timeout": 10,
    }
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Base for models
Base = declarative_base()

async def init_db():
    """Initialize database with pgvector extension and create tables"""
    try:
        async with engine.begin() as conn:
            # Enable pgvector extension
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("✅ pgvector extension enabled")
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created successfully")
    
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {str(e)}")
        raise

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise
        finally:
            await session.close()
