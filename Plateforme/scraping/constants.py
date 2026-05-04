"""
Non‑numeric constants for the scraping module.

This file centralises string‑valued identifiers, API base URLs, model
names, and user‑agent strings that were previously scattered across
individual source files.

Import any constant you need::

    from scraping.constants import USER_AGENTS, GROQ_API_BASE
"""

from __future__ import annotations

import os

# Canonical category source of truth used across scraping registries, model
# choices, and management commands.
CANONICAL_CATEGORIES: list[str] = [
    "events",
    "tools",
    "courses",
    "news",
    "opportunities",
    "corpus",
<<<<<<< HEAD
=======
    "laws",
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
]

CATEGORY_META: dict[str, dict[str, str]] = {
    "events": {
        "label": "Events",
        "label_ar": "الفعاليات",
        "icon": "calendar",
        "color": "blue",
        "model_app": "events",
        "model_name": "Event",
    },
    "tools": {
        "label": "Tools",
        "label_ar": "الأدوات",
        "icon": "wrench",
        "color": "purple",
        "model_app": "resources",
        "model_name": "NLPTool",
    },
    "courses": {
        "label": "Courses",
        "label_ar": "الدورات",
        "icon": "academic-cap",
        "color": "green",
        "model_app": "resources",
        "model_name": "Course",
    },
    "news": {
        "label": "News",
        "label_ar": "الأخبار",
        "icon": "newspaper",
        "color": "yellow",
        "model_app": "QA",
        "model_name": "Post",
    },
    "opportunities": {
        "label": "Opportunities",
        "label_ar": "الفرص",
        "icon": "briefcase",
        "color": "orange",
        "model_app": "pages",
        "model_name": "Opportunity",
    },
    "corpus": {
        "label": "Corpus",
        "label_ar": "المدونات اللغوية",
        "icon": "database",
        "color": "red",
        "model_app": "resources",
        "model_name": "Corpus",
    },
<<<<<<< HEAD
=======
    "laws": {
        "label": "Laws",
        "label_ar": "القوانين",
        "icon": "balance-scale",
        "color": "gray",
        "model_app": "resources",
        "model_name": "Law",
    },
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
}

# ---------------------------------------------------------------------------
# API base URLs
# ---------------------------------------------------------------------------

GROQ_API_BASE: str = "https://api.groq.com/openai/v1"
"""Base URL for the Groq LLM API (OpenAI-compatible endpoint)."""

ARXIV_API_BASE: str = "http://export.arxiv.org/api/query"
"""arXiv OAI API endpoint for paper searches."""

SEMANTIC_SCHOLAR_API_BASE: str = "https://api.semanticscholar.org/graph/v1"
"""Semantic Scholar Academic Graph API v1 base URL."""

HUGGINGFACE_API_BASE: str = "https://huggingface.co/api"
"""HuggingFace Hub API base URL."""

ROR_API_BASE: str = "https://api.ror.org/v2/organizations"
"""ROR v2 API endpoint for institution lookups."""

OPENALEX_API_BASE: str = "https://api.openalex.org/institutions"
"""OpenAlex institution endpoint."""

WAYBACK_API_BASE: str = "https://archive.org/wayback/available"
"""Wayback Machine availability API endpoint."""

WIKICFP_BASE: str = "http://www.wikicfp.com"
"""WikiCFP base URL for CFP scraping."""

CONFERENCE_ALERTS_BASE: str = "https://conferencealerts.com"
"""ConferenceAlerts.com base URL."""

GITHUB_API_BASE: str = "https://api.github.com"
"""GitHub REST API base URL."""

GITHUB_WEB_HOST: str = "github.com"
"""Canonical GitHub web host used for URL parsing."""

GITHUB_API_VERSION: str = "2022-11-28"
"""Pinned GitHub API version header value."""

ARXIV_ABS_BASE: str = "https://export.arxiv.org/abs"
"""Base URL for arXiv abstract pages by arXiv identifier."""

ROR_WEB_BASE: str = "https://ror.org"
"""Base URL for public ROR organization identifiers."""

# ---------------------------------------------------------------------------
# Embedding model identifiers
# ---------------------------------------------------------------------------

DEDUP_EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"
"""Sentence‑Transformers model used for deduplication embeddings (384‑d)."""

DEDUP_EMBEDDING_DIM: int = 384
"""Dimensionality of the dedup embedding vectors."""

# ---------------------------------------------------------------------------
# LLM model identifiers
# ---------------------------------------------------------------------------

GROQ_DEFAULT_MODEL: str = "llama3-8b-8192"
"""Default Groq model used for scraping validation / enrichment."""

GROQ_FALLBACK_MODEL: str = "llama-3.3-70b-versatile"
"""Fallback Groq model when the primary is unavailable."""

# ---------------------------------------------------------------------------
# spaCy NER defaults
# ---------------------------------------------------------------------------

SPACY_DEFAULT_MODEL: str = "en_core_web_sm"
"""Default spaCy model used for English NER extraction."""

SPACY_DEFAULT_MODEL_AR: str = "xx_ent_wiki_sm"
"""Default multilingual spaCy model used for Arabic NER extraction."""

SPACY_NER_LABEL_MAP: dict[str, str] = {
    "PERSON": "PERSON",
    "PER": "PERSON",
    "ORG": "ORG",
    "GPE": "GPE",
    "LOC": "GPE",
    "FAC": "GPE",
    "NORP": "ORG",
    "DATE": "DATE",
    "TIME": "DATE",
    "EVENT": "EVENT",
    "WORK_OF_ART": "TECH",
    "LANGUAGE": "TECH",
    "PRODUCT": "TECH",
    "MISC": "TECH",
}
"""Map raw spaCy labels into normalized entity buckets used by scraping."""

# ---------------------------------------------------------------------------
# User‑Agent pool
# ---------------------------------------------------------------------------

USER_AGENTS: tuple[str, ...] = (
    (
        "Mozilla/5.0 (compatible; NLPPlatformBot/1.0; "
        "+https://github.com/nlp-platform; research purposes)"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.3 Safari/605.1.15"
    ),
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
)
"""Rotating pool of User‑Agent strings for HTTP requests."""

DEFAULT_USER_AGENT: str = USER_AGENTS[0]
"""Canonical bot UA string used when only one is needed."""

# ---------------------------------------------------------------------------
# HTTP defaults
# ---------------------------------------------------------------------------

DEFAULT_ACCEPT: str = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
"""Default Accept header value for HTML scraping requests."""

DEFAULT_ACCEPT_LANGUAGE: str = "en-US,en;q=0.5"
"""Default Accept-Language header value."""

SKIP_HTTP_STATUSES: frozenset[int] = frozenset({403, 404, 422})
"""HTTP status codes that should be skipped immediately (no retry)."""

# ---------------------------------------------------------------------------
# Category registry keys
# ---------------------------------------------------------------------------

CATEGORY_EVENTS: str = "events"
CATEGORY_TOOLS: str = "tools"
CATEGORY_COURSES: str = "courses"

CATEGORY_NEWS: str = "news"
CATEGORY_OPPORTUNITIES: str = "opportunities"
CATEGORY_CORPUS: str = "corpus"

ALL_CATEGORIES: tuple[str, ...] = tuple(CANONICAL_CATEGORIES)
"""Exhaustive tuple of valid scraping category keys."""

EVENT_PRIORITY_SCORES: dict[str, int] = {
    "global": int(os.getenv("SCRAPING_EVENT_PRIORITY_GLOBAL", "25")),
    "regional": int(os.getenv("SCRAPING_EVENT_PRIORITY_REGIONAL", "50")),
    "local": int(os.getenv("SCRAPING_EVENT_PRIORITY_LOCAL", "75")),
}
"""Priority scores applied to event candidates by geographic scope."""

EVENT_DEFAULT_DISCOVERY_PATHS: list[str] = os.getenv(
    "SCRAPING_EVENT_DISCOVERY_PATHS",
    "/events,/conferences,/workshops,/agenda,/seminars",
).split(",")
"""Default HTML listing paths used by the event scraper when none are configured."""

SCRAPER_BOT_EMAIL: str = os.getenv(
    "SCRAPING_BOT_EMAIL", "scraper-bot@nlp-platform.local"
)
"""Contact email attached to scraper-generated records."""

# ---------------------------------------------------------------------------
# Source-tier heuristic tokens
# ---------------------------------------------------------------------------

SOURCE_TIER_TOKEN_MAP: dict[int, tuple[str, ...]] = {
    1: (".dz", "alger", "algeria", "dgrsdt", "mesrs"),
    2: (
        "arab",
        "mena",
        "morocco",
        "tunisia",
        "egypt",
        "saudi",
        "uae",
        "qatar",
        "jordan",
        "oman",
        "lebanon",
    ),
    3: ("africa", "african", "indaba", "masakhane"),
}
"""Token heuristics used to infer source regional tier from name and URL."""

# ---------------------------------------------------------------------------
# ScrapingRun statuses
# ---------------------------------------------------------------------------

RUN_STATUS_RUNNING: str = "running"
RUN_STATUS_COMPLETED: str = "completed"
RUN_STATUS_FAILED: str = "failed"

# ---------------------------------------------------------------------------
# Queue and retry defaults
# ---------------------------------------------------------------------------

SCRAPING_CELERY_QUEUE: str = "scraping"
"""Celery queue name used by scraping tasks."""

DEAD_LETTER_INITIAL_RETRY_COUNT: int = 0
"""Initial retry counter used when recording first dead-letter entry."""

# ---------------------------------------------------------------------------
# Validation verdicts
# ---------------------------------------------------------------------------

VERDICT_GREEN: str = "GREEN"
VERDICT_YELLOW: str = "YELLOW"
VERDICT_RED: str = "RED"
VERDICT_PENDING: str = "PENDING"
VERDICT_UNKNOWN: str = "UNKNOWN"

DEDUP_RULE_UNKNOWN: str = "unknown"
"""Metrics label used when dedup reason cannot be normalized."""

# ---------------------------------------------------------------------------
# Dead‑letter & checkpoint file naming
# ---------------------------------------------------------------------------

DEAD_LETTER_PREFIX: str = "dead_"
"""Filename prefix used for dead‑letter JSON files."""

CHECKPOINT_PREFIX: str = "checkpoint_"
"""Filename prefix used for checkpoint JSON files."""

# ---------------------------------------------------------------------------
# Skip‑reason codes (mirrors ScrapedItemMeta.SKIP_REASON_CHOICES)
# ---------------------------------------------------------------------------

SKIP_DEDUP_URL: str = "dedup_url"
SKIP_DEDUP_NAME: str = "dedup_name"
SKIP_DEDUP_SIMILARITY: str = "dedup_similarity"
SKIP_DEDUP_EMBEDDING: str = "dedup_embedding"
SKIP_DEDUP_DOI: str = "dedup_doi"
SKIP_DEDUP_ARXIV: str = "dedup_arxiv"
SKIP_DEDUP_ROR: str = "dedup_ror"
SKIP_DOWNLOAD_FAIL: str = "download_fail"
SKIP_VALIDATION_FAIL: str = "validation_fail"
SKIP_ENRICHMENT_FAIL: str = "enrichment_fail"
SKIP_CIRCUIT_OPEN: str = "circuit_open"

ALL_SKIP_REASONS: tuple[str, ...] = (
    SKIP_DEDUP_URL,
    SKIP_DEDUP_NAME,
    SKIP_DEDUP_SIMILARITY,
    SKIP_DEDUP_EMBEDDING,
    SKIP_DEDUP_DOI,
    SKIP_DEDUP_ARXIV,
    SKIP_DEDUP_ROR,
    SKIP_DOWNLOAD_FAIL,
    SKIP_VALIDATION_FAIL,
    SKIP_ENRICHMENT_FAIL,
    SKIP_CIRCUIT_OPEN,
)
"""All recognised skip-reason codes."""

# ---------------------------------------------------------------------------
# Custom scraper selector and cleanup defaults
# ---------------------------------------------------------------------------

CUSTOM_SELECTOR_TITLE_FALLBACK: str = "h2, h3"
CUSTOM_SELECTOR_DESC_FALLBACK: str = "p"
CUSTOM_SELECTOR_LINK_FALLBACK: str = "a"
"""Fallback CSS selectors used when source-specific selectors are missing."""

CUSTOM_SCRAPER_CLEANUP_TAGS: tuple[str, ...] = (
    "nav",
    "footer",
    "script",
    "style",
    "header",
    "aside",
    "advertisement",
    "ads",
    "cookie",
    "popup",
    "modal",
    "sidebar",
    "menu",
)
"""Tag names removed from scraped HTML before extraction."""

CUSTOM_SCRAPER_CLEANUP_SELECTORS: tuple[str, ...] = (
    '[class*="nav"]',
    '[class*="menu"]',
    '[class*="footer"]',
    '[class*="header"]',
    '[class*="ad"]',
    '[class*="cookie"]',
    '[id*="nav"]',
    '[id*="menu"]',
    '[id*="footer"]',
    '[id*="header"]',
)
"""CSS selectors removed from scraped HTML before extraction."""

# ---------------------------------------------------------------------------
# Scheduler command constants
# ---------------------------------------------------------------------------

LEGACY_FIXED_SCHEDULE_NAMES: tuple[str, ...] = (
    "Auto-scrape Events Weekly",
    "Auto-scrape Tools Weekly",
    "Auto-scrape Courses Monthly",
)
"""Legacy periodic-task names disabled by sync_scraping_schedules command."""

SCHEDULE_TABLE_NAME_WIDTH: int = 20
"""Display width for source name column in show_schedules output."""

# ---------------------------------------------------------------------------
# System scraper user credentials
# ---------------------------------------------------------------------------

SYSTEM_USER_EMAIL: str = "scraper-bot@nlp-platform.local"
"""Email address for the system scraper bot user."""

SYSTEM_USER_NAME: str = "System Scraper Bot"
"""Display name for the system scraper bot user."""

SYSTEM_USER_NAME_AR: str = "روبوت نظام الاستخراج"
"""Arabic display name for the system scraper bot user."""

# ---------------------------------------------------------------------------
# PDF extraction defaults
# ---------------------------------------------------------------------------

PDF_MAX_BYTES: int = 50 * 1024 * 1024  # 50 MB
"""Maximum raw PDF size in bytes before aborting download."""

PDF_MAX_PAGES: int = 3
"""Number of leading pages to extract text from."""

PDF_MAX_CHARS: int = 12_000
"""Maximum characters of extracted PDF text to keep."""

PDF_DOWNLOAD_TIMEOUT: int = 30
"""Timeout in seconds for PDF HTTP downloads."""

PDF_SECTION_MAX_CHARS: int = 2_000
"""Maximum characters kept per extracted section."""

# ---------------------------------------------------------------------------
# Redis cache alias
# ---------------------------------------------------------------------------

REDIS_CACHE_ALIAS: str = "default"
"""Alias used for the default Redis cache connection."""

# ---------------------------------------------------------------------------
# PDF URL patterns
# ---------------------------------------------------------------------------
PDF_URL_PATTERNS: list[str] = os.getenv(
    "SCRAPING_PDF_URL_PATTERNS", "arxiv.org/pdf/,/pdf/,/download/"
).split(",")
"""List of URL substrings that strongly suggest a PDF file."""

# ---------------------------------------------------------------------------
# Scraper Registry
# ---------------------------------------------------------------------------

SCRAPER_REGISTRY: dict[str, str] = {
    "events": "scraping.scrapers.events.EventScraper",
    "tools": "scraping.scrapers.tools.ToolScraper",
    "courses": "scraping.scrapers.courses.CourseScraper",
    "news": "scraping.scrapers.news.NewsScraper",
    "opportunities": "scraping.scrapers.opportunities.OpportunityScraper",
    "corpus": "scraping.scrapers.corpus.CorpusScraper",
}
"""Map of category to scraper class path for dynamic loading."""
