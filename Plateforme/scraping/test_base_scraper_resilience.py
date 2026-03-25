from unittest.mock import MagicMock

import pytest
import requests

from scraping.models import ScrapingSourceHealth
from scraping.scrapers.base import BaseScraper


class DummyScraper(BaseScraper):
    name = "Dummy"
    category = "news"

    def scrape(self):
        return []


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
