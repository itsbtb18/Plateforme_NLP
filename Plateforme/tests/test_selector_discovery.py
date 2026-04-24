from __future__ import annotations

from types import SimpleNamespace

from scraping.scrapers.selector_discovery import (
    CANDIDATE_PATTERNS,
    SelectorDiscoveryEngine,
)


def _resp(html: str, status_code: int = 200):
    payload = html.encode("utf-8")

    def _raise_for_status():
        if status_code >= 400:
            raise RuntimeError(f"http {status_code}")

    return SimpleNamespace(
        content=payload,
        status_code=status_code,
        raise_for_status=_raise_for_status,
    )


def test_discover_sample_urls_filters_internal_content_links(monkeypatch):
    engine = SelectorDiscoveryEngine()
    homepage = """
    <html><body>
      <a href="/news/2026/03/sample-article">article</a>
      <a href="https://example.com/news/2026/03/another-article">article2</a>
      <a href="https://external.org/news/2026/03/outside">outside</a>
      <a href="/static/site.css">css</a>
      <a href="/n">short</a>
    </body></html>
    """

    monkeypatch.setattr(engine, "_http_get", lambda url: _resp(homepage))

    urls = engine._discover_sample_urls("https://example.com", count=5)

    assert urls == [
        "https://example.com/news/2026/03/sample-article",
        "https://example.com/news/2026/03/another-article",
    ]


def test_score_patterns_tracks_hits_and_text_lengths(monkeypatch):
    engine = SelectorDiscoveryEngine(min_content_length=10)
    html_page = """
    <html><head>
      <meta property="og:title" content="A Long Enough Title Example" />
      <meta name="author" content="Alice Writer" />
    </head><body>
      <h1 class="entry-title">A Long Enough Title Example</h1>
      <div class="entry-content">This is a meaningful summary block with enough content length.</div>
      <time datetime="2026-03-26">2026-03-26</time>
      <div class="author">Alice Writer</div>
    </body></html>
    """
    monkeypatch.setattr(engine, "_http_get", lambda url: _resp(html_page))

    scores = engine._score_patterns(
        [
            "https://example.com/news/a",
            "https://example.com/news/b",
        ]
    )

    assert scores["title"]["h1.entry-title"].hits == 2
    assert scores["summary"][".entry-content"].hits == 2
    assert scores["date"]["time[datetime]"].hits == 2
    assert scores["author"][".author"].hits == 2


def test_get_top_recommendations_respects_min_occurrence_ratio():
    engine = SelectorDiscoveryEngine(min_occurrence_ratio=0.6)
    engine._last_sample_count = 5

    empty = {field: {} for field in CANDIDATE_PATTERNS}

    # One weak pattern appears only once out of five -> filtered out.
    from scraping.scrapers.selector_discovery import SelectorScore

    empty["title"]["h1"] = SelectorScore(hits=1, total_length=80, specificity_sum=0.1)

    recommendations = engine._get_top_recommendations(empty)

    assert recommendations["title"] == []


def test_discover_returns_recommendations_and_confidence(monkeypatch):
    engine = SelectorDiscoveryEngine(min_content_length=10)

    monkeypatch.setattr(
        engine,
        "_discover_sample_urls",
        lambda domain_url, count=5: [
            "https://example.com/news/1",
            "https://example.com/news/2",
            "https://example.com/news/3",
        ],
    )

    html_page = """
    <html><head>
      <meta name="author" content="Editorial Team" />
    </head><body>
      <h1 class="entry-title">Arabic NLP News Item</h1>
      <div class="entry-content">Detailed NLP article summary with enough body text to pass thresholds.</div>
      <time datetime="2026-03-26">2026-03-26</time>
      <div class="author">Editorial Team</div>
    </body></html>
    """
    monkeypatch.setattr(engine, "_http_get", lambda url: _resp(html_page))

    result = engine.discover("https://example.com")

    assert result["domain"] == "https://example.com"
    assert result["sample_count"] == 3
    assert "recommendations" in result
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["recommendations"]["title"]


def test_compute_confidence_returns_zero_for_empty_scores():
    engine = SelectorDiscoveryEngine()
    scores = {field: {} for field in CANDIDATE_PATTERNS}

    confidence = engine._compute_confidence(scores)

    assert confidence == 0.0
