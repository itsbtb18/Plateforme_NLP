from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database
    DATABASE_URL: str = ""

    # Qdrant
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str | None = None
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_PREFER_GRPC: bool = True

    # Elasticsearch
    ELASTICSEARCH_HOST: str = "http://elasticsearch:9200"

    # Redis / Celery
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # Groq API — Chatbot (User-facing)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Groq API — Internal (Classification, Rewriting, Faithfulness)
    GROQ_INTERNAL_API_KEY: str = ""
    GROQ_INTERNAL_MODEL: str = "llama-3.1-8b-instant"

    GROQ_MAX_TOKENS: int = 2048
    GROQ_TEMPERATURE: float = 0.7

    # Embeddings
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIMENSION: int = 1024

    # App Settings
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8001

    # Vector Search
    TOP_K_RESULTS: int = 5
    SIMILARITY_THRESHOLD: float = 0.65

    # Rate Limiting
    MAX_REQUESTS_PER_MINUTE: int = 30

    # Document Processing
    MAX_UPLOAD_SIZE_MB: int = 20
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    MAX_CHUNKS_PER_DOC: int = 500

    # Chat Memory
    MAX_HISTORY_MESSAGES: int = 20
    HISTORY_SUMMARY_THRESHOLD: int = 12
    TOKEN_BUDGET_HISTORY: int = 1500
    TOKEN_BUDGET_SUMMARY: int = 500

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance"""
    return Settings()
