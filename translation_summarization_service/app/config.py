from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    REDIS_URL: str = "redis://redis:6379/0"

    TS_GEMINI_API_KEY: str = ""
    TS_GEMINI_API_KEYS: str = ""
    TS_GEMINI_MODEL: str = "gemini-2.0-flash"

    TS_GROQ_API_KEY: str = ""
    TS_GROQ_API_KEYS: str = ""
    TS_GROQ_TRANSLATION_MODEL: str = "llama-3.3-70b-versatile"
    TS_GROQ_SUMMARIZATION_MODEL: str = "llama-3.3-70b-versatile"

    # Allowed values: "gemini" or "groq"
    TS_PRIMARY_PROVIDER: str = "gemini"
    TS_FALLBACK_PROVIDER: str = "groq"

    # Optional simple auth between gateway/services
    TS_SERVICE_API_KEY: str = ""

    # Cache for repeated translation/summarization requests.
    TS_CACHE_TTL_SECONDS: int = 604800

    # Request scheduling and stability.
    TS_MAX_CONCURRENT_REQUESTS: int = 1
    TS_RATE_LIMIT_BUCKET_CAPACITY: int = 20
    TS_RATE_LIMIT_REFILL_WINDOW_SECONDS: int = 60
    TS_QUEUE_MAX_SIZE_PER_USER: int = 20
    TS_QUEUE_WAIT_TIMEOUT_SECONDS: int = 900
    TS_PROVIDER_GEMINI_BUCKET_CAPACITY: int = 5
    TS_PROVIDER_GEMINI_BUCKET_WINDOW_SECONDS: int = 5
    TS_PROVIDER_GROQ_BUCKET_CAPACITY: int = 5
    TS_PROVIDER_GROQ_BUCKET_WINDOW_SECONDS: int = 5
    TS_GLOBAL_REQUESTS_PER_MINUTE: int = 120

    # Resilience for large inputs: exponential retry when provider returns rate-limit responses.
    TS_RATE_LIMIT_MAX_RETRIES: int = 5
    TS_RATE_LIMIT_BASE_DELAY_SECONDS: float = 10.0
    TS_RATE_LIMIT_MAX_WAIT_SECONDS: float = 60.0
    TS_PROVIDER_HARD_QUOTA_COOLDOWN_SECONDS: float = 300.0
    # Short per-provider timeout and circuit breaker for resilience
    TS_PROVIDER_TIMEOUT_SECONDS: float = 60.0
    TS_CIRCUIT_BREAKER_THRESHOLD: int = 100
    TS_CIRCUIT_BREAKER_COOLDOWN_SECONDS: float = 30.0
    TS_PROVIDER_CALL_DELAY_SECONDS: float = 0.0
    TS_PROVIDER_MAX_CONCURRENCY: int = 5

    TS_INTER_CHUNK_DELAY_SECONDS: float = 0.0
    TS_TRANSLATION_CHUNK_SIZE: int = 3200
    TS_TRANSLATION_CHUNK_OVERLAP: int = 160
    TS_TRANSLATION_MAX_CHUNKS_PER_DOCUMENT: int = 8
    TS_GOOGLE_FALLBACK_CHUNK_SIZE: int = 1800
    TS_PROVIDER_HTTP_TIMEOUT_SECONDS: float = 420.0
    TS_PROVIDER_OPERATION_TIMEOUT_SECONDS: float = 8.0
    TS_SUMMARIZATION_PROVIDER_PHASE_TIMEOUT_SECONDS: float = 15.0
    TS_SUMMARIZE_HTTP_HARD_TIMEOUT_SECONDS: float = 20.0
    TS_GLOBAL_MUTEX_WAIT_SECONDS: float = 8.0

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
