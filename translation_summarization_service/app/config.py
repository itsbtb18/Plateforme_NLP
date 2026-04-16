from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    TS_GEMINI_API_KEY: str = ""
    TS_GEMINI_MODEL: str = "gemini-2.0-flash"

    TS_GROQ_API_KEY: str = ""
    TS_GROQ_TRANSLATION_MODEL: str = "llama-3.3-70b-versatile"
    TS_GROQ_SUMMARIZATION_MODEL: str = "llama-3.3-70b-versatile"

    # Allowed values: "gemini" or "groq"
    TS_PRIMARY_PROVIDER: str = "gemini"
    TS_FALLBACK_PROVIDER: str = "groq"

    # Optional simple auth between gateway/services
    TS_SERVICE_API_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
