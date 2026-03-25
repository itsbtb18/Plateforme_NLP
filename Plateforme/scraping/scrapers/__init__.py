"""
Scraper registry — maps category names to scraper classes.
"""

from .courses import CourseScraper
from .events import EventScraper
from .institutions import InstitutionScraper
from .news import NewsScraper
from .tools import ToolScraper

SCRAPERS = {
    "events": EventScraper,
    "tools": ToolScraper,
    "news": NewsScraper,
    "courses": CourseScraper,
    "institutions": InstitutionScraper,
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
        "description": "Arabic NLP models, LLMs, speech models, and datasets from HuggingFace Hub",
        "sources": [
            "HuggingFace Model Hub API",
            "Curated Arabic LLMs & Speech Models",
            "Curated HuggingFace Arabic Datasets",
        ],
    },
    "news": {
        "label": "News",
        "icon": "fa-newspaper",
        "color": "#f59e0b",
        "description": "Recent NLP research papers and publications",
        "sources": ["arXiv API (cs.CL)", "Semantic Scholar API"],
    },
    "courses": {
        "label": "Courses",
        "icon": "fa-graduation-cap",
        "color": "#3b82f6",
        "description": "NLP courses from top universities, Coursera, and YouTube",
        "sources": [
            "MIT OpenCourseWare",
            "Coursera NLP Courses",
            "YouTube NLP Playlists",
            "Curated University Courses",
        ],
    },
    "institutions": {
        "label": "Institutions",
        "icon": "fa-university",
        "color": "#8b5cf6",
        "description": "Universities, research centres, and NLP labs worldwide",
        "sources": [
            "ROR API",
            "OpenAlex API",
            "Algerian Universities",
            "African & Arabic NLP Labs",
            "North African Institutions (Morocco, Tunisia, Egypt, Libya)",
            "Arabic/Gulf Institutions (SA, UAE, QA, JO, LB, OM, SD)",
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
