from __future__ import annotations

from types import SimpleNamespace

from scraping.scrapers.base_http_scraper import BaseHTTPScraper
from scraping.scrapers.wayback_fallback import MockResponse, WaybackMachineFallback


def _fake_response(json_payload=None, text="", status_code=200):
    def _raise_for_status():
        if status_code >= 400:
            raise RuntimeError(f"http {status_code}")

    payload = {
        "status_code": status_code,
        "text": text,
        "raise_for_status": _raise_for_status,
    }
    if json_payload is not None:
        payload["json"] = lambda: json_payload
    return SimpleNamespace(**payload)


def test_find_best_snapshot_returns_web_archive_url(monkeypatch):
    fb = WaybackMachineFallback()

    cdx_payload = [
        ["timestamp", "statuscode", "original"],
        ["20260301010101", "200", "https://example.com/news/post"],
    ]

    monkeypatch.setattr(
        fb.session,
        "get",
        lambda *args, **kwargs: _fake_response(json_payload=cdx_payload),
    )

    snapshot = fb._find_best_snapshot("https://example.com/news/post", max_age_days=90)

    assert (
        snapshot
        == "https://web.archive.org/web/20260301010101/https://example.com/news/post"
    )


def test_find_best_snapshot_returns_none_when_no_rows(monkeypatch):
    fb = WaybackMachineFallback()

    monkeypatch.setattr(
        fb.session,
        "get",
        lambda *args, **kwargs: _fake_response(
            json_payload=[["timestamp", "statuscode", "original"]]
        ),
    )

    snapshot = fb._find_best_snapshot("https://example.com/news/post", max_age_days=90)

    assert snapshot is None


def test_get_latest_snapshot_returns_mock_response(monkeypatch):
    fb = WaybackMachineFallback()
    monkeypatch.setattr(
        fb,
        "_find_best_snapshot",
        lambda url, max_age_days=90: (
            "https://web.archive.org/web/20260301010101/https://example.com/news/post"
        ),
    )

    html = """
    <html><body>
      <div id="wm-ipp">toolbar</div>
      <script src="https://archive.org/script.js"></script>
      <article><h1>Recovered Content</h1></article>
    </body></html>
    """
    monkeypatch.setattr(
        fb.session,
        "get",
        lambda *args, **kwargs: _fake_response(text=html, status_code=200),
    )

    result = fb.get_latest_snapshot("https://example.com/news/post", max_age_days=90)

    assert isinstance(result, MockResponse)
    assert result.source == "wayback"
    assert "Recovered Content" in result.text
    assert "wm-ipp" not in result.text
    assert "archive.org/script.js" not in result.text


def test_strip_wayback_toolbar_removes_known_elements():
    fb = WaybackMachineFallback()
    html = """
    <html><body>
      <div id="wm-ipp-base">base</div>
      <div id="wm-toolbar">toolbar</div>
      <script src="https://archive.org/foo.js"></script>
      <main>Actual Content</main>
    </body></html>
    """

    cleaned = fb.strip_wayback_toolbar(html)

    assert "wm-ipp-base" not in cleaned
    assert "wm-toolbar" not in cleaned
    assert "archive.org/foo.js" not in cleaned
    assert "Actual Content" in cleaned


class _FakeCircuitBreaker:
    def __init__(self):
        self._open = False

    def is_open(self):
        return self._open

    def record_failure(self, error_type):
        return None


class _DummyHTTPScraper(BaseHTTPScraper):
    category = "news"

    def __init__(self):
        # Intentionally avoid BaseHTTPScraper.__init__ to skip Redis coupling in tests.
        self.circuit_breaker = _FakeCircuitBreaker()
        self._network_failures = {}

    def scrape(self):
        return None


def test_handle_network_failure_uses_wayback_for_dns(monkeypatch):
    scraper = _DummyHTTPScraper()

    fallback_response = MockResponse(
        "<html><body>archived</body></html>",
        "https://example.com/news/post",
        source="wayback",
        archived_snapshot_url="https://web.archive.org/web/20260301010101/https://example.com/news/post",
    )

    monkeypatch.setattr(
        WaybackMachineFallback,
        "get_latest_snapshot",
        lambda self, url, max_age_days=90: fallback_response,
    )

    called = {"metrics": False}

    def _update_metrics(error_type, domain):
        called["metrics"] = True

    monkeypatch.setattr(scraper, "_update_metrics", _update_metrics)

    result = scraper._handle_network_failure(
        "https://example.com/news/post",
        "example.com",
        "dns_failure",
        source_name="example-source",
    )

    assert result is fallback_response
    # In success fallback path, normal network-failure metric path is not used.
    assert called["metrics"] is False
