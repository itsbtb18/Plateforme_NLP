"""
Scraper registry — maps category names to scraper classes.
"""

from .events import EventScraper
from .tools import ToolScraper
from .news import NewsScraper
from .courses import CourseScraper
from .institutions import InstitutionScraper

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
        "sources": ["WikiCFP", "Curated NLP Conference List"],
    },
    "tools": {
        "label": "Tools",
        "icon": "fa-tools",
        "color": "#10b981",
        "description": "Arabic NLP models and tools from HuggingFace Hub",
        "sources": ["HuggingFace Model Hub API"],
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
        "description": "NLP courses from top universities worldwide",
        "sources": ["MIT OpenCourseWare", "Curated University Courses"],
    },
    "institutions": {
        "label": "Institutions",
        "icon": "fa-university",
        "color": "#8b5cf6",
        "description": "Universities and research centres active in NLP",
        "sources": ["ROR API", "OpenAlex API"],
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
