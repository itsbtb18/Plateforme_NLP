"""
Scraper registry — maps category names to scraper classes.
"""

from .corpus import CorpusScraper
from .courses import CourseScraper
from .events import EventScraper
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
}

CATEGORY_META = {
    "events": {
        "label": "Events",
        "icon": "fa-calendar-alt",
        "color": "#6366f1",
        "description": "NLP conferences, workshops, seminars, and calls for papers",
        "sources": [
            "WikiCFP",
            "ConferenceAlerts (Algeria, Morocco, Tunisia, Egypt)",
            "AllConferenceAlert Algeria",
            "Curated NLP Conference List",
            "Curated Arabic/MENA NLP Events",
        ],
    },
    "tools": {
        "label": "Tools",
        "icon": "fa-tools",
        "color": "#10b981",
        "description": "Arabic NLP models, LLMs, speech models, and datasets",
        "sources": [
            "Curated Arabic LLMs & Speech Models",
            "Curated HuggingFace Arabic Datasets",
        ],
    },
    "courses": {
        "label": "Courses",
        "icon": "fa-graduation-cap",
        "color": "#3b82f6",
        "description": "NLP courses from universities and curated learning providers",
        "sources": [
            "Curated University Courses",
        ],
    },
    "news": {
        "label": "News",
        "icon": "fa-newspaper",
        "color": "#f59e0b",
        "description": "Arabic NLP and AI news and research highlights",
        "sources": [
            "Tavily Search + Groq",
        ],
    },
    "opportunities": {
        "label": "Opportunities",
        "icon": "fa-briefcase",
        "color": "#0ea5e9",
        "description": "PhD, PostDoc, jobs, and grants in NLP/AI",
        "sources": [
            "Tavily Search + Groq",
        ],
    },
    "corpus": {
        "label": "Corpus",
        "icon": "fa-database",
        "color": "#14b8a6",
        "description": "Arabic NLP datasets and corpora",
        "sources": [
            "Tavily Search + Groq",
        ],
    },
}


def get_scraper(category: str):
    """Return a fresh scraper instance for the given category."""
    scraper_cls = SCRAPERS.get(category)
    if scraper_cls is None:
        raise ValueError(f"Unknown scraper category: {category}")
    return scraper_cls()


def get_all_categories():
    """Return an ordered list of (key, meta) tuples."""
    return [(k, CATEGORY_META[k]) for k in SCRAPERS]
