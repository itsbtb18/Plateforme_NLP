from types import SimpleNamespace

import pytest
from scraping.scrapers.events import EventScraper
from scraping.scrapers.news import NewsScraper

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


@pytest.fixture
def event_scraper(monkeypatch):
    scraper = EventScraper()
    return scraper


@pytest.fixture
def news_scraper(monkeypatch):
    scraper = NewsScraper()
    return scraper


def test_events_uses_only_configured_active_sources(event_scraper, monkeypatch):
    configured_source = SimpleNamespace(
        name="My Selected Source",
        url="https://example.org",
        base_url="",
        scrape_config={
            "paths": ["/agenda"],
            "default_location": "Algeria",
            "priority_score": 70,
            "tier": 2,
            "timeout": 9,
        },
    )
    monkeypatch.setattr(
        event_scraper, "get_active_sources", lambda: [configured_source]
    )

    collected_kwargs = {}
    monkeypatch.setattr(
        event_scraper,
        "_collect_from_source",
        lambda **kwargs: collected_kwargs.update(kwargs) or [{"title": "x"}],
    )
    monkeypatch.setattr(
        event_scraper,
        "_deduplicate_combined_candidates",
        lambda items: items,
    )

    saved = []
    monkeypatch.setattr(
        event_scraper, "_save_event_candidate", lambda item: saved.append(item)
    )

    event_scraper.scrape()

    assert collected_kwargs["base_url"] == "https://example.org"
    assert collected_kwargs["source_name"] == "My Selected Source"
    assert collected_kwargs["paths"] == ["/agenda"]
    assert collected_kwargs["default_location"] == "Algeria"
    assert collected_kwargs["priority"] == 70
    assert collected_kwargs["tier"] == 2
    assert collected_kwargs["timeout"] == 9
    assert len(saved) == 1


def test_events_with_no_active_sources_does_not_use_hidden_fallback(
    event_scraper, monkeypatch
):
    monkeypatch.setattr(event_scraper, "get_active_sources", lambda: [])
    monkeypatch.setattr(event_scraper, "_get_default_sources", lambda: [])

    save_calls = []
    monkeypatch.setattr(
        event_scraper, "_save_event_candidate", lambda item: save_calls.append(item)
    )

    event_scraper.scrape()

    assert save_calls == []


def test_news_processes_sources_in_priority_order(news_scraper, monkeypatch):
    calls = []

    def make_tier(name, payload):
        def _tier():
            calls.append(name)
            return payload

        return _tier

    monkeypatch.setattr(
        news_scraper,
        "_scrape_tier_1_algerian_research_news",
        make_tier("tier1", []),
    )
    monkeypatch.setattr(
        news_scraper,
        "_scrape_tier_4_global_research_papers",
        make_tier("tier4", []),
    )
    monkeypatch.setattr("scraping.intelligence.generate_queries", lambda category: [])

    news_scraper.scrape()

    assert calls == ["tier1", "tier4"]


def test_event_dedup_combined_candidates_prefers_higher_priority(event_scraper):
    a = {
        "title": "Same Event",
        "website": "https://x.example.org/e1",
        "start_date": "2026-09-10",
        "priority_score": 25,
        "source_name": "Low",
    }
    b = {
        "title": "Same Event",
        "website": "https://x.example.org/e1",
        "start_date": "2026-09-10",
        "priority_score": 100,
        "source_name": "High",
    }

    deduped = event_scraper._deduplicate_combined_candidates([a, b])

    assert len(deduped) == 1
    assert deduped[0]["priority_score"] == 100
