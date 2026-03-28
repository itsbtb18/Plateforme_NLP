from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import requests
from bs4 import BeautifulSoup

from scraping.models import ScrapingSource, ScrapingSourceHealth
from scraping.scrapers.base import BaseScraper
from scraping.scrapers.playwright_scraper import PlaywrightFallbackScraper


class DummyScraper(BaseScraper):
    name = "Dummy"
    category = "news"

    def scrape(self):
        return []


class DummyPlaywrightScraper(PlaywrightFallbackScraper):
    name = "DummyPlaywright"
    category = "news"

    def __init__(self):
        BaseScraper.__init__(self)

    def scrape(self):
        return []


class AllowAllCircuitBreaker:
    def allow_request(self, _domain):
        return True

    def record_success(self, _domain):
        return None

    def record_failure(self, _domain):
        return None


def _response(status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(f"{status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


@pytest.mark.django_db
def test_safe_request_retries_on_500(monkeypatch):
    scraper = DummyScraper()
    calls = [_response(500), _response(500), _response(200)]

    monkeypatch.setattr(scraper.session, "get", MagicMock(side_effect=calls))
    monkeypatch.setattr("scraping.scrapers.base.time.sleep", lambda *_: None)

    result = scraper.safe_request("https://example.com/api", source_name="RetrySource")

    assert result is not None
    assert result.status_code == 200
    assert scraper.session.get.call_count == scraper.MAX_RETRIES


@pytest.mark.django_db
def test_safe_request_respects_timeout(monkeypatch):
    scraper = DummyScraper()
    monkeypatch.setattr(
        scraper.session,
        "get",
        MagicMock(side_effect=requests.Timeout("timed out")),
    )
    monkeypatch.setattr("scraping.scrapers.base.time.sleep", lambda *_: None)

    result = scraper.safe_request(
        "https://example.com/timeout",
        source_name="TimeoutSource",
    )

    assert result is None
    health = ScrapingSourceHealth.objects.get(
        category="news", source_name="TimeoutSource"
    )
    assert health.total_failures >= 1
    assert health.last_error


@pytest.mark.django_db
def test_safe_request_circuit_open_skips_request(monkeypatch):
    scraper = DummyScraper()
    ScrapingSourceHealth.objects.create(
        category="news",
        source_name="CircuitSource",
        circuit_state="open",
    )

    get_mock = MagicMock(return_value=_response(200))
    monkeypatch.setattr(scraper.session, "get", get_mock)

    result = scraper.safe_request(
        "https://example.com/blocked",
        source_name="CircuitSource",
    )

    assert result is None
    get_mock.assert_not_called()


@pytest.mark.django_db
def test_safe_request_user_agent_rotates(monkeypatch):
    scraper = DummyScraper()
    observed_agents = []

    def fake_choice(options):
        idx = len(observed_agents) % len(options)
        return options[idx]

    def fake_get(*args, **kwargs):
        observed_agents.append(scraper.session.headers.get("User-Agent"))
        return _response(200)

    monkeypatch.setattr("scraping.scrapers.base.secure_choice", fake_choice)
    monkeypatch.setattr(scraper.session, "get", fake_get)

    for _ in range(10):
        scraper.safe_request("https://example.com/ok", source_name="UASource")

    assert len(set(observed_agents)) >= 2


@pytest.mark.django_db
def test_safe_request_records_response_time(monkeypatch):
    scraper = DummyScraper()

    monkeypatch.setattr(scraper.session, "get", MagicMock(return_value=_response(200)))
    monotonic_values = iter([100.0, 100.1])
    monkeypatch.setattr(
        "scraping.scrapers.base.time.monotonic",
        lambda: next(monotonic_values),
    )

    scraper.safe_request("https://example.com/fast", source_name="TimingSource")

    health = ScrapingSourceHealth.objects.get(
        category="news", source_name="TimingSource"
    )
    assert health.avg_response_time is not None
    assert health.avg_response_time > 0


@pytest.mark.django_db
def test_safe_request_uses_source_verify_ssl(monkeypatch):
    scraper = DummyScraper()
    scraper._domain_circuit_breaker = AllowAllCircuitBreaker()
    source_name = f"SSLBypassSource-{uuid4()}"
    source_url = f"https://ssl-{uuid4().hex}.example.com"
    source_stub = MagicMock()
    source_stub.name = source_name
    source_stub.is_active = True
    source_stub.verify_ssl = False
    source_stub.proxy_url = ""
    source_stub.fail_count = 0
    source_stub.consecutive_failures = 0

    monkeypatch.setattr(
        scraper,
        "_resolve_source_context",
        lambda *_args, **_kwargs: source_stub,
    )
    monkeypatch.setattr(scraper, "_mark_source_success", lambda *_args, **_kwargs: None)

    captured = {}

    def fake_get(*args, **kwargs):
        captured.update(kwargs)
        return _response(200)

    monkeypatch.setattr(
        "scraping.scrapers.base.can_fetch", lambda *_args, **_kwargs: True
    )
    monkeypatch.setattr(scraper.session, "get", fake_get)

    result = scraper.safe_request(
        f"{source_url}/page",
        source_name=source_name,
    )

    assert result is not None
    assert captured.get("verify") is False


@pytest.mark.django_db
def test_force_playwright_source_bypasses_static_fetch(monkeypatch):
    scraper = DummyPlaywrightScraper()
    scraper._domain_circuit_breaker = AllowAllCircuitBreaker()
    source_name = f"ForcePlaywrightSource-{uuid4()}"
    ScrapingSource.objects.create(
        name=source_name,
        category="news",
        url="https://force-playwright.example.com",
        force_playwright=True,
        is_active=True,
    )

    safe_request_mock = MagicMock(return_value=_response(200))
    playwright_mock = MagicMock(return_value=("<html>rendered</html>", "playwright"))

    monkeypatch.setattr(scraper, "safe_request", safe_request_mock)
    monkeypatch.setattr(scraper, "_playwright_fetch", playwright_mock)

    html, method = scraper.fetch_with_fallback(
        "https://force-playwright.example.com/events",
        source_name=source_name,
    )

    assert method == "playwright"
    assert "rendered" in html
    safe_request_mock.assert_not_called()
    playwright_mock.assert_called_once()


@pytest.mark.django_db
def test_paginate_listing_respects_source_max_pages(monkeypatch):
    scraper = DummyScraper()
    visited_urls = []

    def fake_fetch_listing_page(url, timeout=None):
        visited_urls.append(url)
        return BeautifulSoup(
            f"<html><body><a href='/x'>{url}</a></body></html>", "html.parser"
        )

    monkeypatch.setattr(scraper, "fetch_listing_page", fake_fetch_listing_page)

    items = scraper.paginate_listing(
        listing_url="https://example.org/news",
        extract_fn=lambda *, soup, page_url: [page_url],
        scrape_config={"max_pages": 2},
    )

    assert len(visited_urls) == 2
    assert visited_urls[0] == "https://example.org/news"
    assert visited_urls[1] == "https://example.org/news?page=2"
    assert len(items) == 2


@pytest.mark.django_db
def test_paginate_listing_stops_on_repeated_page_content(monkeypatch):
    scraper = DummyScraper()
    fetch_calls = []

    def fake_fetch_listing_page(url, timeout=None):
        fetch_calls.append(url)
        return BeautifulSoup(
            "<html><body><div>same-content</div></body></html>", "html.parser"
        )

    monkeypatch.setattr(scraper, "fetch_listing_page", fake_fetch_listing_page)

    items = scraper.paginate_listing(
        listing_url="https://example.org/events",
        extract_fn=lambda *, soup, page_url: [f"candidate:{page_url}"],
        scrape_config={"max_pages": 10},
    )

    # page=2 is fetched once, then loop stops because page content fingerprint repeats.
    assert len(fetch_calls) == 2
    assert len(items) == 1


@pytest.mark.django_db
def test_extract_with_admin_selectors_returns_mapped_fields():
    scraper = DummyScraper()
    source = MagicMock()
    source.url = "https://selectors.example.org"
    source.css_selectors = {
        "title_selector": ".title",
        "desc_selector": ".body",
        "date_selector": "time",
        "author_selector": ".author",
        "link_selector": "a.read-more",
        "image_selector": "img.cover",
    }

    soup = BeautifulSoup(
        """
        <article>
          <h2 class='title'>Admin Headline</h2>
          <p class='body'>Admin extracted body text.</p>
          <time datetime='2026-03-01'>1 Mar 2026</time>
          <span class='author'>Selector Bot</span>
          <a class='read-more' href='/post/1'>Read</a>
          <img class='cover' data-src='/img/cover.jpg' />
        </article>
        """,
        "html.parser",
    )

    result = scraper._extract_with_admin_selectors(soup, source)

    assert result is not None
    assert result["title"] == "Admin Headline"
    assert result["body"] == "Admin extracted body text."
    assert result["date_raw"] == "2026-03-01"
    assert result["author"] == "Selector Bot"
    assert result["url"] == "/post/1"
    assert result["image_url"] == "/img/cover.jpg"


@pytest.mark.django_db
def test_extract_with_admin_selectors_returns_none_without_title_selector():
    scraper = DummyScraper()
    source = MagicMock()
    source.css_selectors = {}

    soup = BeautifulSoup("<article><h2>Fallback title</h2></article>", "html.parser")

    assert scraper._extract_with_admin_selectors(soup, source) is None
