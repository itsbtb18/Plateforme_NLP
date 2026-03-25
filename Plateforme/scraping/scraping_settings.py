import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _as_bool(value: str, default: bool = False) -> bool:
    raw = (value or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ScrapingSettings:
    # HTTP
    request_timeout: int = int(os.environ.get("SCRAPING_TIMEOUT", "30"))
    max_retries: int = int(os.environ.get("SCRAPING_MAX_RETRIES", "3"))
    backoff_base: float = float(os.environ.get("SCRAPING_BACKOFF_BASE", "2.0"))
    backoff_max: float = float(os.environ.get("SCRAPING_BACKOFF_MAX", "60.0"))

    # Downloads
    max_file_size_mb: int = int(os.environ.get("SCRAPING_MAX_FILE_MB", "50"))
    download_enabled: bool = _as_bool(
        os.environ.get("SCRAPING_DOWNLOAD_ENABLED", "true"),
        default=True,
    )
    max_concurrent_downloads: int = int(
        os.environ.get(
            "SCRAPING_MAX_CONCURRENT_DL",
            os.environ.get("SCRAPING_MAX_CONCURRENT_DOWNLOADS", "3"),
        )
    )

    # Circuit breaker
    circuit_threshold: float = float(
        os.environ.get("SCRAPING_CIRCUIT_THRESHOLD", "0.3")
    )
    circuit_cooldown: int = int(os.environ.get("SCRAPING_CIRCUIT_COOLDOWN", "300"))

    # Robots
    respect_robots: bool = _as_bool(
        os.environ.get("SCRAPING_RESPECT_ROBOTS", "true"),
        default=True,
    )

    # LLM
    llm_api_key: str = os.environ.get("GROQ_API_KEY", "")
    llm_model: str = os.environ.get("SCRAPING_LLM_MODEL", "llama3-8b-8192")
    llm_timeout: int = int(os.environ.get("SCRAPING_LLM_TIMEOUT", "30"))
    llm_max_retries: int = int(os.environ.get("SCRAPING_LLM_MAX_RETRIES", "2"))

    # Security
    allowed_download_domains: list[str] = field(
        default_factory=lambda: [
            domain.strip()
            for domain in os.environ.get("SCRAPING_ALLOWED_DOMAINS", "").split(",")
            if domain.strip()
        ]
    )

    def validate(self) -> None:
        errors: list[str] = []

        if self.request_timeout < 1 or self.request_timeout > 300:
            errors.append(f"SCRAPING_TIMEOUT={self.request_timeout} must be 1-300")
        if self.max_retries < 0 or self.max_retries > 10:
            errors.append(f"SCRAPING_MAX_RETRIES={self.max_retries} must be 0-10")
        if self.backoff_base <= 0:
            errors.append(f"SCRAPING_BACKOFF_BASE={self.backoff_base} must be > 0")
        if self.backoff_max < self.backoff_base:
            errors.append("SCRAPING_BACKOFF_MAX must be >= SCRAPING_BACKOFF_BASE")
        if self.max_file_size_mb < 1 or self.max_file_size_mb > 500:
            errors.append(f"SCRAPING_MAX_FILE_MB={self.max_file_size_mb} must be 1-500")
        if self.max_concurrent_downloads < 1 or self.max_concurrent_downloads > 50:
            errors.append(
                "SCRAPING_MAX_CONCURRENT_DL="
                f"{self.max_concurrent_downloads} must be 1-50"
            )
        if self.circuit_threshold <= 0:
            errors.append(
                f"SCRAPING_CIRCUIT_THRESHOLD={self.circuit_threshold} must be > 0"
            )
        if self.circuit_cooldown < 0 or self.circuit_cooldown > 86_400:
            errors.append(
                f"SCRAPING_CIRCUIT_COOLDOWN={self.circuit_cooldown} must be 0-86400"
            )
        if self.llm_timeout < 1 or self.llm_timeout > 300:
            errors.append(f"SCRAPING_LLM_TIMEOUT={self.llm_timeout} must be 1-300")
        if self.llm_max_retries < 0 or self.llm_max_retries > 10:
            errors.append(
                f"SCRAPING_LLM_MAX_RETRIES={self.llm_max_retries} must be 0-10"
            )

        if errors:
            raise ValueError("Invalid scraping configuration:\n" + "\n".join(errors))


_settings: ScrapingSettings | None = None


def get_scraping_settings() -> ScrapingSettings:
    global _settings
    if _settings is None:
        _settings = ScrapingSettings()
        _settings.validate()
        logger.info(
            "scraping_settings_loaded",
            extra={
                "request_timeout": _settings.request_timeout,
                "max_retries": _settings.max_retries,
                "respect_robots": _settings.respect_robots,
            },
        )
    return _settings
