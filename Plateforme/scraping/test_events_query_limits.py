# pyright: reportMissingImports=false

from scraping.scrapers.events import EventScraper
from scraping.scraping_settings import scraping_settings as SS


def test_events_custom_prompts_not_capped_to_default_limit(monkeypatch):
    scraper = EventScraper()
    prompts = [f"custom prompt {index}" for index in range(1, 31)]

    monkeypatch.setattr(
        scraper,
        "get_active_search_queries",
        lambda category: prompts,
    )

    queries = scraper._build_search_queries()

    assert queries == prompts
    assert len(queries) == 30


def test_events_default_templates_still_honor_query_limit(monkeypatch):
    scraper = EventScraper()

    monkeypatch.setattr(scraper, "get_active_search_queries", lambda category: [])
    monkeypatch.setattr(SS, "EVENTS_SEARCH_QUERY_LIMIT", 14, raising=False)

    queries = scraper._build_search_queries()

    assert 0 < len(queries) <= 14
