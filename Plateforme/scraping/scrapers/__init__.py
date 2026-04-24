"""
Scraper registry — maps category names to scraper classes.
"""

from scraping.constants import (
    CANONICAL_CATEGORIES,
)
from scraping.constants import (
    CATEGORY_META as CANONICAL_CATEGORY_META,
)

from .corpus import CorpusScraper
from .courses import CourseScraper
from .events import EventScraper
from .laws import LawScraper
from .news import NewsScraper
from .opportunities import OpportunityScraper
from .tools import ToolScraper

SCRAPERS = {
    "events": EventScraper,
    "tools": ToolScraper,
    "courses": CourseScraper,
    "news": NewsScraper,
    "opportunities": OpportunityScraper,
    "corpus": CorpusScraper,
    "laws": LawScraper,
}

_ICON_TO_FA = {
    "calendar": "fa-calendar-alt",
    "wrench": "fa-tools",
    "academic-cap": "fa-graduation-cap",
    "newspaper": "fa-newspaper",
    "briefcase": "fa-briefcase",
    "database": "fa-database",
}

_COLOR_TO_HEX = {
    "blue": "#6366f1",
    "purple": "#10b981",
    "green": "#3b82f6",
    "yellow": "#f59e0b",
    "orange": "#0ea5e9",
    "red": "#14b8a6",
}

_CATEGORY_DESCRIPTIONS = {
    "events": "NLP conferences, workshops, seminars, and calls for papers",
    "tools": "Arabic NLP models, LLMs, speech models, and datasets",
    "courses": "NLP courses from universities and curated learning providers",
    "news": "Arabic NLP and AI news and research highlights",
    "opportunities": "PhD, PostDoc, jobs, and grants in NLP/AI",
    "corpus": "Arabic NLP datasets and corpora",
    "laws": "Arabic NLP legal frameworks, AI regulations, and policy documents",
}

_CATEGORY_SOURCES = {
    "events": [
        "WikiCFP",
        "ConferenceAlerts (Algeria, Morocco, Tunisia, Egypt)",
        "AllConferenceAlert Algeria",
        "Curated NLP Conference List",
        "Curated Arabic/MENA NLP Events",
    ],
    "tools": [
        "Curated Arabic LLMs & Speech Models",
        "Curated HuggingFace Arabic Datasets",
    ],
    "courses": [
        "Curated University Courses",
    ],
    "news": [
        "Tavily Search + Groq",
    ],
    "opportunities": [
        "Tavily Search + Groq",
    ],
    "corpus": [
        "Tavily Search + Groq",
    ],
    "laws": [
        "Tavily Search + Groq",
    ],
}

CATEGORY_META = {
    category: {
        "label": CANONICAL_CATEGORY_META[category]["label"],
        "label_ar": CANONICAL_CATEGORY_META[category]["label_ar"],
        "icon": _ICON_TO_FA.get(
            CANONICAL_CATEGORY_META[category]["icon"],
            f"fa-{CANONICAL_CATEGORY_META[category]['icon']}",
        ),
        "color": _COLOR_TO_HEX.get(
            CANONICAL_CATEGORY_META[category]["color"],
            "#6366f1",
        ),
        "description": _CATEGORY_DESCRIPTIONS.get(category, ""),
        "sources": _CATEGORY_SOURCES.get(category, []),
        "model_app": CANONICAL_CATEGORY_META[category]["model_app"],
        "model_name": CANONICAL_CATEGORY_META[category]["model_name"],
    }
    for category in CANONICAL_CATEGORIES
    if category in SCRAPERS
}


def get_scraper(category: str):
    """Return a fresh scraper instance for the given category."""
    scraper_cls = SCRAPERS.get(category)
    if scraper_cls is None:
        raise ValueError(f"Unknown scraper category: {category}")
    return scraper_cls()


def get_all_categories():
    """Return an ordered list of (key, meta) tuples."""
    return [(category, CATEGORY_META[category]) for category in CANONICAL_CATEGORIES]
