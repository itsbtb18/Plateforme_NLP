"""
Centralised scraping configuration — single source of truth.

Every configurable numeric/boolean value used anywhere in the ``scraping``
package is declared here.  Values are loaded once from environment variables
(falling back to documented defaults) and exposed as a frozen dataclass
singleton.

Usage::

    from scraping.scraping_settings import scraping_settings

    timeout = scraping_settings.CONNECT_TIMEOUT
    max_items = scraping_settings.RSS_MAX_ITEMS
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from scraping.constants import SPACY_DEFAULT_MODEL, SPACY_DEFAULT_MODEL_AR

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _env(key: str, default: str) -> str:
    """Read an env var with a fallback default."""
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    return int(_env(key, str(default)))


def _env_float(key: str, default: float) -> float:
    return float(_env(key, str(default)))


def _env_float_tuple(key: str, default: tuple[float, ...]) -> tuple[float, ...]:
    raw = _env(key, ",".join(str(v) for v in default))
    try:
        values = tuple(float(part.strip()) for part in raw.split(",") if part.strip())
    except ValueError:
        logger.warning("Invalid float tuple for %s=%r; using default", key, raw)
        return default
    return values or default


def _env_bool(key: str, default: bool) -> bool:
    raw = _env(key, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _django_int_setting(key: str, default: int) -> int:
    """Read an int from Django settings with a safe fallback."""
    try:
        from django.conf import settings as django_settings

        return int(getattr(django_settings, key, default))
    except Exception:
        return default


def _django_path_setting(key: str, default: str) -> Path:
    """Read a filesystem path from Django settings with a safe fallback."""
    try:
        from django.conf import settings as django_settings

        return Path(str(getattr(django_settings, key, default)))
    except Exception:
        return Path(str(default))


# ---------------------------------------------------------------------------
# ScrapingSettings dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScrapingSettings:
    """Centralised configuration for the entire scraping module.

    Every field is loaded from an environment variable with a documented
    default.  The class is frozen to prevent accidental mutation.  Access
    the module‑level singleton via ``scraping_settings``.
    """

    # ── TIMEOUTS ────────────────────────────────────────────────────────
    CONNECT_TIMEOUT: float = _env_float("SCRAPING_CONNECT_TIMEOUT", 3.0)
    """TCP connect timeout in seconds."""

    READ_TIMEOUT: float = _env_float("SCRAPING_READ_TIMEOUT", 7.0)
    """HTTP body read timeout in seconds."""

    TOTAL_TIMEOUT: float = _env_float("SCRAPING_TOTAL_TIMEOUT", 10.0)
    """Overall per-request timeout in seconds."""

    LLM_TIMEOUT: float = _env_float("SCRAPING_LLM_TIMEOUT", 30.0)
    """Timeout for LLM API calls in seconds."""

    HEAD_TIMEOUT: float = _env_float("SCRAPING_HEAD_TIMEOUT", 10.0)
    """Timeout for HEAD preflight requests in seconds."""

    GLOBAL_FALLBACK_PROXY: str = _env("SCRAPING_GLOBAL_FALLBACK_PROXY", "")
    """Fallback proxy URL when a source has no proxy configured."""

    WAYBACK_MAX_AGE_DAYS: int = _env_int("SCRAPING_WAYBACK_MAX_AGE_DAYS", 90)
    """Maximum age in days for Wayback Machine snapshots."""

    SOURCE_TEST_CACHE_TTL: int = _env_int("SCRAPING_SOURCE_TEST_TTL_SECONDS", 1800)
    """Cache TTL in seconds for source reachability test results."""

    # ── RETRY POLICY ────────────────────────────────────────────────────
    MAX_RETRIES: int = _env_int("SCRAPING_MAX_RETRIES", 3)
    """Maximum number of HTTP request retries."""

    RETRY_BACKOFF_BASE: int = _env_int("SCRAPING_RETRY_BACKOFF_BASE", 30)
    """Base delay in seconds for exponential retry backoff."""

    RETRY_BACKOFF_CAP: int = _env_int("SCRAPING_RETRY_BACKOFF_CAP", 180)
    """Maximum delay in seconds for retry backoff."""

    RETRY_AFTER_BUFFER: int = _env_int("SCRAPING_RETRY_AFTER_BUFFER", 2)
    """Extra seconds added to Retry-After header values."""

    # ── RATE LIMITS ─────────────────────────────────────────────────────
    MAX_CONCURRENT_DOWNLOADS: int = _env_int("SCRAPING_MAX_CONCURRENT_DOWNLOADS", 4)
    """Maximum parallel media downloads per scraper run."""

    METRICS_LAG_INTERVAL: int = _env_int("SCRAPING_METRICS_LAG_INTERVAL", 60)
    """Minimum seconds between queue‑lag metric updates."""

    METRICS_SCRAPE_DURATION_BUCKETS: tuple[float, ...] = _env_float_tuple(
        "SCRAPING_METRICS_SCRAPE_DURATION_BUCKETS",
        (0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300, 600, 1200),
    )
    """Histogram buckets for category-level scrape duration metrics."""

    METRICS_SOURCE_DURATION_BUCKETS: tuple[float, ...] = _env_float_tuple(
        "SCRAPING_METRICS_SOURCE_DURATION_BUCKETS",
        (0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300, 600, 1200),
    )
    """Histogram buckets for source-level scrape duration metrics."""

    METRICS_ENRICHMENT_DURATION_BUCKETS: tuple[float, ...] = _env_float_tuple(
        "SCRAPING_METRICS_ENRICHMENT_DURATION_BUCKETS",
        (0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30),
    )
    """Histogram buckets for enrichment step duration metrics."""

    # ── DEDUPLICATION POLICY ────────────────────────────────────────────
    JACCARD_THRESHOLD: float = _env_float("SCRAPING_JACCARD_THRESHOLD", 0.75)
    """Jaccard similarity threshold for loose deduplication."""

    STRICT_JACCARD: float = _env_float("SCRAPING_STRICT_JACCARD", 0.80)
    """Jaccard similarity threshold for strict deduplication."""

    SEMANTIC_FALLBACK: float = _env_float("SCRAPING_SEMANTIC_FALLBACK", 0.75)
    """Cosine similarity threshold for semantic dedup fallback."""

    DEDUP_WINDOW: int = _env_int("SCRAPING_DEDUP_WINDOW", 500)
    """Number of recent items to search for duplicates."""

    DEDUP_DATE_OVERLAP_DAYS: int = _env_int("SCRAPING_DEDUP_DATE_OVERLAP_DAYS", 3)
    """Allowed date gap in days before two items are considered distinct."""

    # ── FRESHNESS WINDOWS (days) ────────────────────────────────────────
    FRESHNESS_NEWS: int = _env_int("SCRAPING_FRESHNESS_NEWS_DAYS", 30)
    FRESHNESS_EVENTS: int = _env_int("SCRAPING_FRESHNESS_EVENTS_DAYS", 730)
    FRESHNESS_COURSES: int = _env_int("SCRAPING_FRESHNESS_COURSES_DAYS", 730)
    FRESHNESS_TOOLS: int = _env_int("SCRAPING_FRESHNESS_TOOLS_DAYS", 365)
    FRESHNESS_INSTITUTIONS: int = _env_int("SCRAPING_FRESHNESS_INST_DAYS", 365)

    # ── ENRICHMENT POLICY ───────────────────────────────────────────────
    MAX_TOPICS: int = _env_int("SCRAPING_ENRICH_MAX_TOPICS", 5)
    """Maximum topics extracted per item."""

    MAX_KEYWORDS: int = _env_int("SCRAPING_ENRICH_MAX_KEYWORDS", 8)
    """Maximum keywords extracted per item."""

    SPACY_MODEL: str = _env("SCRAPING_SPACY_MODEL", SPACY_DEFAULT_MODEL)
    """spaCy model used for default (non-Arabic) NER extraction."""

    SPACY_MODEL_AR: str = _env("SCRAPING_SPACY_MODEL_AR", SPACY_DEFAULT_MODEL_AR)
    """spaCy model used for Arabic NER extraction."""

    SPACY_MAX_CHARS: int = _env_int("SCRAPING_SPACY_MAX_CHARS", 50_000)
    """Maximum text length sent to spaCy NER pipeline per item."""

    LLM_CONFIDENCE_THRESHOLD: float = _env_float("SCRAPING_LLM_CONFIDENCE", 0.70)
    """Minimum LLM confidence to accept a classification."""

    LLM_MAX_TOKENS: int = _env_int("SCRAPING_LLM_MAX_TOKENS", 50)
    """Max output tokens for short classification LLM calls."""

    # ── STORAGE LIMITS ──────────────────────────────────────────────────
    MAX_DOCUMENT_MB: int = _env_int("SCRAPING_MAX_DOCUMENT_MB", 50)
    """Maximum downloadable document size in megabytes."""

    MAX_IMAGE_MB: int = _env_int("SCRAPING_MAX_IMAGE_MB", 10)
    """Maximum downloadable image size in megabytes."""

    DOWNLOAD_CHUNK_BYTES: int = _env_int("SCRAPING_DOWNLOAD_CHUNK_BYTES", 8192)
    """Chunk size in bytes for streamed downloads."""

    TRUNCATE_SUMMARY_LEN: int = _env_int("SCRAPING_TRUNCATE_SUMMARY_LEN", 200)
    """Maximum length for truncated summary strings."""

    # ── SCRAPING LIMITS ─────────────────────────────────────────────────
    RSS_MAX_ITEMS: int = _env_int("SCRAPING_RSS_MAX_ITEMS", 50)
    """Maximum items to process from a single RSS/Atom feed."""

    RSS_DESCRIPTION_MIN_LEN: int = _env_int("SCRAPING_RSS_DESC_MIN_LEN", 200)
    """Minimum RSS description length before full-page fetch."""

    NEWS_ABSTRACT_MIN_LEN: int = _env_int("SCRAPING_NEWS_ABSTRACT_MIN_LEN", 120)
    """Minimum article abstract length for institutional news pages."""

    NEWS_MAX_ARTICLES_PER_SOURCE: int = _env_int("SCRAPING_NEWS_MAX_ARTICLES", 20)
    """Maximum news articles ingested per source in one run."""

    RSS_FULL_CONTENT_MAX_CHARS: int = _env_int("SCRAPING_RSS_MAX_CHARS", 3000)
    """Maximum characters kept from an RSS full-content field."""

    LISTING_MAX_CONTAINERS: int = _env_int("SCRAPING_LISTING_MAX_CONTAINERS", 180)
    """Maximum listing containers parsed from a single page."""

    MAX_PAGES_DEFAULT: int = _env_int("SCRAPING_MAX_PAGES_DEFAULT", 3)
    """Default maximum number of listing pages to crawl per source/path."""

    MAX_PAGES_HARD_LIMIT: int = _env_int("SCRAPING_MAX_PAGES_HARD_LIMIT", 10)
    """Absolute hard cap for listing pagination to prevent runaway loops."""

    ARXIV_RESULTS_PER_PAGE: int = _env_int("SCRAPING_ARXIV_PAGE_SIZE", 20)
    """Number of arXiv results requested per API page."""

    ARXIV_MAX_TOTAL: int = _env_int("SCRAPING_ARXIV_MAX_TOTAL", 100)
    """Maximum total arXiv papers fetched in one scraper run."""

    S2_MAX_TOTAL: int = _env_int("SCRAPING_S2_MAX_TOTAL", 100)
    """Maximum total Semantic Scholar papers fetched per query."""

    S2_QUERY_LIMIT: int = _env_int("SCRAPING_S2_QUERY_LIMIT", 20)
    """Maximum number of Semantic Scholar results requested per API page."""

    EVENTS_COMPLETENESS_MIN: int = _env_int("SCRAPING_EVENTS_COMPLETENESS_MIN", 20)
    """Minimum completeness score required before saving an event."""

    MIN_CONFIDENCE_TO_SAVE: float = _env_float("SCRAPING_MIN_CONFIDENCE_TO_SAVE", 0.35)
    """Minimum normalized confidence (0-1) required to save a scraped item."""

    EVENTS_MIN_ITEMS_PER_RUN: int = _env_int("SCRAPING_EVENTS_MIN_ITEMS_PER_RUN", 10)
    """Target minimum number of event items to save per run when available."""

    EVENTS_SEARCH_QUERY_LIMIT: int = _env_int("SCRAPING_EVENTS_SEARCH_QUERY_LIMIT", 14)
    """Maximum number of Tavily queries executed in one events run."""

    PROMPT_MAX_ACTIVE_PER_CATEGORY: int = _env_int(
        "SCRAPING_PROMPT_MAX_ACTIVE_PER_CATEGORY",
        _django_int_setting("GEMINI_SCRAPING_MAX_RPD", 50),
    )
    """Maximum active prompts allowed per category to reduce free-tier LLM quota pressure."""

    EVENTS_EXTRACTION_BATCH_SIZE: int = _env_int(
        "SCRAPING_EVENTS_EXTRACTION_BATCH_SIZE", 8
    )
    """Number of Tavily rows sent per LLM extraction batch."""

    EVENTS_EXTRACTION_MAX_BATCHES: int = _env_int(
        "SCRAPING_EVENTS_EXTRACTION_MAX_BATCHES", 4
    )
    """Maximum extraction batches processed per events run."""

    COURSES_COMPLETENESS_MIN: int = _env_int("SCRAPING_COURSES_COMPLETENESS_MIN", 40)
    """Minimum completeness score required before saving a course."""

    MIT_QUERY_LIMIT: int = _env_int("SCRAPING_MIT_QUERY_LIMIT", 10)
    """Number of MIT OCW results requested per topic query."""

    YOUTUBE_MAX_RESULTS: int = _env_int("SCRAPING_YOUTUBE_MAX_RESULTS", 10)
    """Maximum playlists requested per YouTube Data API search."""

    YOUTUBE_PLAYLIST_CAP: int = _env_int("SCRAPING_YOUTUBE_PLAYLIST_CAP", 10)
    """Maximum playlists processed from HTML fallback extraction."""

    DISCOVERY_SAMPLE_COUNT: int = _env_int("SCRAPING_DISCOVERY_SAMPLE_COUNT", 5)
    """Number of sample pages used for selector discovery."""

    # ── CIRCUIT BREAKER ─────────────────────────────────────────────────
    CIRCUIT_THRESHOLD: float = _env_float("SCRAPING_CIRCUIT_THRESHOLD", 25.0)
    """Health score below which the circuit breaker opens."""

    CIRCUIT_TRIP_COUNT: int = _env_int("SCRAPING_CIRCUIT_TRIP_COUNT", 5)
    """Consecutive failures that trip the circuit breaker."""

    CIRCUIT_COOLDOWN_SECONDS: int = _env_int("SCRAPING_CIRCUIT_COOLDOWN", 300)
    """Seconds an open circuit waits before half‑open probe."""

    FAILURE_PENALTY: float = _env_float("SCRAPING_FAILURE_PENALTY", 15.0)
    """Health‑score points deducted per failure."""

    SUCCESS_RECOVERY: float = _env_float("SCRAPING_SUCCESS_RECOVERY", 10.0)
    """Health‑score points recovered per success."""

    # ── PERSISTENCE ─────────────────────────────────────────────────────
    DEAD_LETTER_DIR: Path = _django_path_setting(
        "SCRAPING_DEAD_LETTER_DIR",
        _env("SCRAPING_DEAD_LETTER_DIR", "logs/scraping_dead_letters"),
    )
    """Directory for dead‑letter log files."""

    CHECKPOINT_DIR: Path = _django_path_setting(
        "SCRAPING_CHECKPOINT_DIR",
        _env("SCRAPING_CHECKPOINT_DIR", "logs/scraping_checkpoints"),
    )
    """Directory for checkpoint state files."""

    CHECKPOINT_TTL: int = _env_int("SCRAPING_CHECKPOINT_TTL", 86400 * 3)
    """Cache TTL in seconds for checkpoint entries (default 3 days)."""

    CHECKPOINT_TOKEN_LEN: int = _env_int("SCRAPING_CHECKPOINT_TOKEN_LEN", 16)
    """Length of the hash token used in checkpoint filenames."""

    # ── ROBOTS POLICY ───────────────────────────────────────────────────
    ROBOTS_TIMEOUT: int = _env_int(
        "SCRAPING_ROBOTS_TIMEOUT",
        _django_int_setting("SCRAPING_ROBOTS_TIMEOUT", 10),
    )
    """Timeout in seconds for robots.txt fetch operations."""

    ROBOTS_CACHE_TTL: int = _env_int("SCRAPING_ROBOTS_CACHE_TTL", 3600)
    """Cache TTL in seconds for parsed robots.txt results."""

    ROBOTS_FAIL_OPEN: bool = _env_bool("SCRAPING_ROBOTS_FAIL_OPEN", True)
    """Allow scraping when robots.txt is unreachable."""

    # ── RATE LIMITING (views) ───────────────────────────────────────────
    VIEW_RATE_DEFAULT: int = _env_int("SCRAPING_VIEW_RATE_DEFAULT", 60)
    """Default max requests per window for view endpoints."""

    VIEW_RATE_WINDOW_SECONDS: int = _env_int("SCRAPING_VIEW_RATE_WINDOW", 60)
    """Rate-limit rolling window size in seconds for scraping views."""

    VIEW_RATE_TRIGGER: int = _env_int("SCRAPING_VIEW_RATE_TRIGGER", 5)
    """Max requests per window for trigger/action endpoints."""

    VIEW_RATE_STANDARD: int = _env_int("SCRAPING_VIEW_RATE_STANDARD", 30)
    """Max requests per window for standard read endpoints."""

    VIEW_RATE_METRICS: int = _env_int("SCRAPING_VIEW_RATE_METRICS", 10)
    """Max requests per window for metrics endpoints."""

    VIEW_RECENT_RUNS_LIMIT: int = _env_int("SCRAPING_VIEW_RECENT_RUNS", 10)
    """Default number of recent runs shown in dashboard views."""

    # ── DEDUP CONFIDENCE ────────────────────────────────────────────────
    FALLBACK_DEDUP_CONFIDENCE: float = _env_float(
        "SCRAPING_FALLBACK_DEDUP_CONF",
        85.0,
    )
    """Default confidence percentage for dedup matches without a score."""

    # ── BACKWARD-COMPAT aliases ─────────────────────────────────────────
    # The old ScrapingSettings used different attribute names.  These
    # read-only properties keep existing call-sites working without edits.

    @property
    def request_timeout(self) -> float:  # noqa: D401
        """Alias kept for backward compatibility."""
        return self.TOTAL_TIMEOUT

    @property
    def max_retries(self) -> int:  # noqa: D401
        """Alias kept for backward compatibility."""
        return self.MAX_RETRIES

    @property
    def backoff_base(self) -> float:  # noqa: D401
        """Alias kept for backward compatibility."""
        return float(self.RETRY_BACKOFF_BASE)

    @property
    def backoff_max(self) -> float:  # noqa: D401
        """Alias kept for backward compatibility."""
        return float(self.RETRY_BACKOFF_CAP)

    @property
    def max_file_size_mb(self) -> int:  # noqa: D401
        """Alias kept for backward compatibility."""
        return self.MAX_DOCUMENT_MB

    @property
    def download_enabled(self) -> bool:  # noqa: D401
        """Alias kept for backward compatibility."""
        return _env_bool("SCRAPING_DOWNLOAD_ENABLED", True)

    @property
    def max_concurrent_downloads(self) -> int:  # noqa: D401
        """Alias kept for backward compatibility."""
        return self.MAX_CONCURRENT_DOWNLOADS

    @property
    def circuit_threshold(self) -> float:  # noqa: D401
        """Alias kept for backward compatibility."""
        return self.CIRCUIT_THRESHOLD

    @property
    def circuit_cooldown(self) -> int:  # noqa: D401
        """Alias kept for backward compatibility."""
        return self.CIRCUIT_COOLDOWN_SECONDS

    @property
    def respect_robots(self) -> bool:  # noqa: D401
        """Alias kept for backward compatibility."""
        return _env_bool("SCRAPING_RESPECT_ROBOTS", True)

    @property
    def llm_api_key(self) -> str:  # noqa: D401
        """Alias kept for backward compatibility."""
        return os.environ.get("GROQ_API_KEY", "")

    @property
    def llm_model(self) -> str:  # noqa: D401
        """Alias kept for backward compatibility."""
        return os.environ.get("SCRAPING_LLM_MODEL", "llama3-8b-8192")

    @property
    def llm_timeout(self) -> float:  # noqa: D401
        """Alias kept for backward compatibility."""
        return self.LLM_TIMEOUT

    @property
    def llm_max_retries(self) -> int:  # noqa: D401
        """Alias kept for backward compatibility."""
        return self.MAX_RETRIES

    @property
    def allowed_download_domains(self) -> list[str]:  # noqa: D401
        """Alias kept for backward compatibility."""
        raw = os.environ.get("SCRAPING_ALLOWED_DOMAINS", "")
        return [d.strip() for d in raw.split(",") if d.strip()]

    def validate(self) -> None:
        """Raise ``ValueError`` if any setting is out of range."""
        errors: list[str] = []

        if self.CONNECT_TIMEOUT <= 0:
            errors.append(f"CONNECT_TIMEOUT={self.CONNECT_TIMEOUT} must be > 0")
        if self.READ_TIMEOUT <= 0:
            errors.append(f"READ_TIMEOUT={self.READ_TIMEOUT} must be > 0")
        if self.TOTAL_TIMEOUT <= 0:
            errors.append(f"TOTAL_TIMEOUT={self.TOTAL_TIMEOUT} must be > 0")
        if self.MAX_RETRIES < 0 or self.MAX_RETRIES > 20:
            errors.append(f"MAX_RETRIES={self.MAX_RETRIES} must be 0-20")
        if self.MAX_CONCURRENT_DOWNLOADS < 1 or self.MAX_CONCURRENT_DOWNLOADS > 50:
            errors.append(
                f"MAX_CONCURRENT_DOWNLOADS={self.MAX_CONCURRENT_DOWNLOADS} must be 1-50"
            )
        if self.CIRCUIT_THRESHOLD <= 0:
            errors.append(f"CIRCUIT_THRESHOLD={self.CIRCUIT_THRESHOLD} must be > 0")
        if self.CIRCUIT_COOLDOWN_SECONDS < 0:
            errors.append(
                f"CIRCUIT_COOLDOWN_SECONDS={self.CIRCUIT_COOLDOWN_SECONDS} must be >= 0"
            )
        if self.MAX_DOCUMENT_MB < 1 or self.MAX_DOCUMENT_MB > 500:
            errors.append(f"MAX_DOCUMENT_MB={self.MAX_DOCUMENT_MB} must be 1-500")

        if errors:
            raise ValueError("Invalid scraping configuration:\n" + "\n".join(errors))


# ---------------------------------------------------------------------------
# Module‑level singleton
# ---------------------------------------------------------------------------

scraping_settings = ScrapingSettings()


def get_scraping_settings() -> ScrapingSettings:
    """Return the module‑level ``ScrapingSettings`` singleton.

    This function is kept for backward compatibility with existing
    call‑sites that used the old factory pattern.
    """
    return scraping_settings
