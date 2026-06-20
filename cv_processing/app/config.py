"""
CV Processing Service Configuration
"""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """CV Processing Service configuration loaded from environment variables"""

    # Service Configuration
    SERVICE_NAME: str = "CV Processing Service"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8002
    DEBUG: bool = False

    # Database (PostgreSQL)
    POSTGRES_USER: str = "nlp_admin"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "nlp_platform"
    
    DATABASE_URL: str = ""

    @property
    def get_database_url(self) -> str:
        """Construct PostgreSQL database URL"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Groq API - CV Processing (Dedicated Key)
    GROQ_CV_API_KEY: str = ""
    GROQ_CV_MODEL: str = "llama-3.3-70b-versatile"

    # Redis / Celery Configuration
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    @property
    def redis_url(self) -> str:
        """Construct Redis URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Celery Configuration
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: list = ["json"]
    CELERY_TIMEZONE: str = "UTC"
    CELERY_ENABLE_UTC: bool = True
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 3600  # 1 hour
    CELERY_TASK_SOFT_TIME_LIMIT: int = 3300  # 55 minutes

    @property
    def get_celery_broker_url(self) -> str:
        """Construct Celery Broker URL"""
        if self.CELERY_BROKER_URL:
            return self.CELERY_BROKER_URL
        return f"{self.redis_url.replace('0', '1')}"  # Use Redis DB 1 for Celery

    @property
    def get_celery_result_backend_url(self) -> str:
        """Construct Celery Result Backend URL"""
        if self.CELERY_RESULT_BACKEND:
            return self.CELERY_RESULT_BACKEND
        return f"{self.redis_url.replace('0', '2')}"  # Use Redis DB 2 for results

    # CV Processing Configuration
    MAX_FILE_SIZE_MB: int = 20
    ALLOWED_FILE_TYPES: list = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
    TEMP_FILE_DIR: str = ""  # Empty string uses system temp directory

    @property
    def get_temp_dir(self) -> str:
        """Get temp directory, using system default if not specified"""
        import tempfile
        if not self.TEMP_FILE_DIR or self.TEMP_FILE_DIR == "/tmp":
            return tempfile.gettempdir()
        return self.TEMP_FILE_DIR

    # Model Configuration
    CV_EXTRACTION_MODEL: str = "groq"  # Can be 'groq', 'gemini', or 'openai'
    GROQ_MAX_TOKENS: int = 2048
    GROQ_TEMPERATURE: float = 0.3

    # CORS Configuration
    CORS_ORIGINS: list = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_HEADERS: list = ["*"]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
