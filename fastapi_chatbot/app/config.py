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

    # Gemini API — Chatbot (User-facing)
    GENAI_API_KEY: str = ""
    GENAI_MODEL: str = "gemini-2.0-flash"

    # Gemini API — Internal (Classification, Rewriting, Faithfulness)
    GENAI_INTERNAL_API_KEY: str = ""
    GENAI_INTERNAL_MODEL: str = "gemini-2.0-flash"

    # Backward-compatible aliases (if older envs use GEMINI_* names)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = ""
    GEMINI_INTERNAL_API_KEY: str = ""
    GEMINI_INTERNAL_MODEL: str = ""

    # Provider selectors (chat vs internal workflows)
    LLM_PROVIDER_CHAT: str = "gemini"
    LLM_PROVIDER_INTERNAL: str = "gemini"
    GROQ_MAX_TOKENS: int = 2048
    GROQ_TEMPERATURE: float = 0.7

    # Embeddings
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIMENSION: int = 1024

    # App Settings
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Vector Search
    TOP_K_RESULTS: int = 5
    SIMILARITY_THRESHOLD: float = 0.65

    # Rate Limiting
    MAX_REQUESTS_PER_MINUTE: int = 30

    # AI Gateway security
    AI_JWT_SECRET: str = "change-me"
    AI_JWT_OPTIONAL: bool = True
    AI_RATE_LIMIT_PER_MINUTE: int = 60

    # AI providers
    AI_OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    AI_OPENAI_API_KEY: str = ""
    AI_OPENAI_TRANSLATION_MODEL: str = "gpt-4o-mini"
    AI_OPENAI_SUMMARY_MODEL: str = "gpt-4o-mini"

    AI_LOCAL_PROVIDER_URL: str = "http://localhost:11434"
    AI_LOCAL_TRANSLATION_MODEL: str = "llama3.1:8b"
    AI_LOCAL_SUMMARY_MODEL: str = "llama3.1:8b"

    # AI storage and files
    AI_STORAGE_BUCKET: str = "corpus-ai"
    AI_ENABLE_RESULT_STORAGE: bool = False
    AI_MAX_FILE_SIZE_MB: int = 100
    AI_S3_ENDPOINT: str = "http://minio:9000"
    AI_S3_ACCESS_KEY: str = ""
    AI_S3_SECRET_KEY: str = ""
    AI_S3_REGION: str = "us-east-1"

    # AI caching
    AI_TRANSLATION_CACHE_TTL_SECONDS: int = 604800
    AI_SUMMARY_CACHE_TTL_SECONDS: int = 604800
    AI_EMBEDDINGS_CACHE_TTL_SECONDS: int = 2592000

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

    # Web Search — Exa (RAG fallback retrieval)
    EXA_API_KEY: str = ""
    EXA_ENABLED: bool = False
    EXA_MAX_CALLS_PER_SESSION: int = 10
    EXA_MAX_CALLS_PER_HOUR: int = 30
    EXA_CACHE_TTL_HOURS: int = 24

    # Web Search — Tavily (User-triggered web mode)
    TAVILY_API_KEY: str = ""
    TAVILY_ENABLED: bool = False

    # Translation/Summarization Service (Global Scheduler)
    TS_SERVICE_URL: str = "http://translation_summarization:8010"
    TS_SERVICE_API_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance"""
    return Settings()
