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


def test_events_processes_sources_in_priority_order(event_scraper, monkeypatch):
    calls = []

    def make_tier(name, payload):
        def _tier():
            calls.append(name)
            return payload

        return _tier

    monkeypatch.setattr(event_scraper, "_scrape_tier_1_events", make_tier("tier1", []))
    monkeypatch.setattr(event_scraper, "_scrape_tier_2_events", make_tier("tier2", []))
    monkeypatch.setattr(event_scraper, "_scrape_tier_3_events", make_tier("tier3", []))
    monkeypatch.setattr(event_scraper, "_scrape_tier_4_events", make_tier("tier4", []))
    monkeypatch.setattr(
        event_scraper, "_deduplicate_combined_candidates", lambda items: []
    )

    event_scraper.scrape()

    assert calls == ["tier1", "tier2", "tier3", "tier4"]


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
