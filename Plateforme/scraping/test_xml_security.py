from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup
from defusedxml.common import DefusedXmlException

from scraping.scrapers.base import BaseScraper
from scraping.scrapers.news import NewsScraper


def _resp_with_bytes(payload: bytes):
    response = MagicMock()
    response.content = payload
    return response


@pytest.mark.django_db
def test_defusedxml_blocks_xxe_attack(monkeypatch):
    scraper = NewsScraper()
    scraper._search_terms = []

    payload = b"""<?xml version='1.0' encoding='UTF-8'?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]>
<feed xmlns='http://www.w3.org/2005/Atom'>
  <entry>
    <title>&xxe;</title>
    <summary>malicious</summary>
    <published>2026-01-01T00:00:00Z</published>
  </entry>
</feed>
"""

    monkeypatch.setattr(
        scraper,
        "safe_request",
        lambda *a, **k: _resp_with_bytes(payload),
    )

    with pytest.raises(DefusedXmlException):
        scraper._scrape_arxiv()


@pytest.mark.django_db
def test_oversized_xml_payload_rejected(monkeypatch):
    scraper = NewsScraper()
    scraper._search_terms = []

    huge_payload = b"<x>" + (b"a" * (2_000_001)) + b"</x>"
    monkeypatch.setattr(
        scraper,
        "safe_request",
        lambda *a, **k: _resp_with_bytes(huge_payload),
    )

    result = scraper._scrape_arxiv()

    assert result == []


@pytest.mark.django_db
def test_valid_arxiv_xml_parses_correctly(monkeypatch):
    scraper = NewsScraper()
    scraper._search_terms = []

    xml_payload = b"""<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns='http://www.w3.org/2005/Atom'>
  <entry>
    <title>  A  Test   Paper  </title>
    <summary>  This is   an abstract. </summary>
    <published>2026-02-10T12:00:00Z</published>
    <author><name>Alice</name></author>
    <author><name>Bob</name></author>
    <link rel='alternate' href='https://arxiv.org/abs/2602.00001' />
    <link title='pdf' href='https://arxiv.org/pdf/2602.00001.pdf' type='application/pdf' />
    <category term='cs.CL' />
  </entry>
</feed>
"""
    monkeypatch.setattr(
        scraper,
        "safe_request",
        lambda *a, **k: _resp_with_bytes(xml_payload),
    )

    created = MagicMock()
    monkeypatch.setattr(scraper, "_create_news_post", created)

    scraper._scrape_arxiv()

    assert created.call_count == 1
    kwargs = created.call_args.kwargs
    assert kwargs["title"] == "A Test Paper"
    assert kwargs["abstract"] == "This is an abstract."
    assert kwargs["authors"] == "Alice, Bob"
    assert kwargs["source_url"] == "https://arxiv.org/abs/2602.00001"
    assert kwargs["pdf_url"] == "https://arxiv.org/pdf/2602.00001.pdf"


@pytest.mark.django_db
def test_arxiv_paginates_until_max_total(monkeypatch):
    scraper = NewsScraper.__new__(NewsScraper)
    BaseScraper.__init__(scraper)
    scraper._search_terms = []
    scraper._scraping_settings = SimpleNamespace(
        ARXIV_RESULTS_PER_PAGE=1,
        ARXIV_MAX_TOTAL=2,
    )

    xml_page_1 = b"""<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns='http://www.w3.org/2005/Atom'>
  <entry>
    <title>Paper One</title>
    <summary>Summary one</summary>
    <published>2026-02-10T12:00:00Z</published>
    <author><name>Alice</name></author>
    <link rel='alternate' href='https://arxiv.org/abs/2602.00001' />
    <link title='pdf' href='https://arxiv.org/pdf/2602.00001.pdf' type='application/pdf' />
  </entry>
</feed>
"""
    xml_page_2 = b"""<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns='http://www.w3.org/2005/Atom'>
  <entry>
    <title>Paper Two</title>
    <summary>Summary two</summary>
    <published>2026-02-11T12:00:00Z</published>
    <author><name>Bob</name></author>
    <link rel='alternate' href='https://arxiv.org/abs/2602.00002' />
    <link title='pdf' href='https://arxiv.org/pdf/2602.00002.pdf' type='application/pdf' />
  </entry>
</feed>
"""

    responses_by_start = {
        0: _resp_with_bytes(xml_page_1),
        1: _resp_with_bytes(xml_page_2),
    }
    requested_starts = []

    def fake_safe_request(*_args, **kwargs):
        params = kwargs.get("params") or {}
        start = int(params.get("start", 0))
        requested_starts.append(start)
        return responses_by_start[start]

    monkeypatch.setattr(scraper, "safe_request", fake_safe_request)
    created = MagicMock()
    monkeypatch.setattr(scraper, "_create_news_post", created)

    scraper._scrape_arxiv()

    assert requested_starts == [0, 1]
    assert created.call_count == 2


@pytest.mark.django_db
def test_semantic_scholar_uses_cursor_pagination(monkeypatch):
    scraper = NewsScraper.__new__(NewsScraper)
    BaseScraper.__init__(scraper)
    scraper._scraping_settings = SimpleNamespace(S2_MAX_TOTAL=2)

    calls = []

    def fake_s2_request(params):
        calls.append(dict(params))
        if "next" not in params:
            return {
                "data": [
                    {
                        "paperId": "p1",
                        "title": "Paper 1",
                        "abstract": "A",
                        "url": "https://example.org/p1",
                        "publicationDate": "2026-01-01",
                        "year": 2026,
                        "authors": [{"name": "Author 1"}],
                    }
                ],
                "next": "cursor-1",
            }
        return {
            "data": [
                {
                    "paperId": "p2",
                    "title": "Paper 2",
                    "abstract": "B",
                    "url": "https://example.org/p2",
                    "publicationDate": "2026-01-02",
                    "year": 2026,
                    "authors": [{"name": "Author 2"}],
                }
            ],
            "next": None,
        }

    monkeypatch.setattr(scraper, "_s2_request", fake_s2_request)
    monkeypatch.setattr("scraping.scrapers.news.time.sleep", lambda *_: None)

    created = MagicMock()
    monkeypatch.setattr(scraper, "_create_news_post", created)

    scraper._scrape_semantic_scholar()

    assert len(calls) == 2
    assert "next" not in calls[0]
    assert calls[1].get("next") == "cursor-1"
    assert created.call_count == 2


@pytest.mark.django_db
def test_news_article_prefers_admin_selectors_when_configured(monkeypatch):
    scraper = NewsScraper.__new__(NewsScraper)
    BaseScraper.__init__(scraper)
    scraper._scraping_settings = SimpleNamespace(NEWS_ABSTRACT_MIN_LEN=10)

    source = SimpleNamespace(
        url="https://news.example.org",
        css_selectors={
            "title_selector": ".admin-title",
            "desc_selector": ".admin-body",
            "date_selector": "time",
            "author_selector": ".admin-author",
            "link_selector": "a.admin-link",
            "image_selector": "img.admin-image",
        },
    )

    soup = BeautifulSoup(
        """
        <html><body>
          <h1>Heuristic Title</h1>
          <div class='admin-title'>Admin Title</div>
          <div class='admin-body'>Admin body content that is long enough.</div>
          <time datetime='2026-03-10'>March 10, 2026</time>
          <span class='admin-author'>Admin Author</span>
          <a class='admin-link' href='/news/admin-item'>Read</a>
          <img class='admin-image' src='/media/admin.png' />
        </body></html>
        """,
        "html.parser",
    )

    monkeypatch.setattr(scraper, "fetch_listing_page", lambda *_a, **_k: soup)
    monkeypatch.setattr(
        scraper, "_extract_article_title", lambda *_a, **_k: "Heuristic Title"
    )
    monkeypatch.setattr(
        scraper, "_extract_article_text", lambda *_a, **_k: "Heuristic body"
    )

    created = {}
    monkeypatch.setattr(
        scraper, "_create_news_post", lambda **kwargs: created.update(kwargs)
    )

    scraper._scrape_single_research_article(
        article_url="https://news.example.org/articles/1",
        source_name="Configured Source",
        source=source,
    )

    assert created["title"] == "Admin Title"
    assert created["abstract"] == "Admin body content that is long enough."
    assert created["source_url"] == "https://news.example.org/news/admin-item"
    assert created["thumbnail_url"] == "https://news.example.org/media/admin.png"


@pytest.mark.django_db
def test_news_article_falls_back_to_heuristics_when_selectors_empty(monkeypatch):
    scraper = NewsScraper.__new__(NewsScraper)
    BaseScraper.__init__(scraper)
    scraper._scraping_settings = SimpleNamespace(NEWS_ABSTRACT_MIN_LEN=10)

    source = SimpleNamespace(url="https://news.example.org", css_selectors={})

    soup = BeautifulSoup(
        "<html><body><h1>Heuristic Title</h1><p>Heuristic body with enough length.</p></body></html>",
        "html.parser",
    )

    monkeypatch.setattr(scraper, "fetch_listing_page", lambda *_a, **_k: soup)
    monkeypatch.setattr(
        scraper, "_extract_article_title", lambda *_a, **_k: "Heuristic Title"
    )
    monkeypatch.setattr(
        scraper,
        "_extract_article_text",
        lambda *_a, **_k: "Heuristic body with enough length.",
    )
    monkeypatch.setattr(
        scraper, "_extract_article_date", lambda *_a, **_k: "2026-03-11"
    )
    monkeypatch.setattr(scraper, "_extract_article_image", lambda *_a, **_k: "")

    warning_mock = MagicMock()
    monkeypatch.setattr("scraping.scrapers.news.logger.warning", warning_mock)

    created = {}
    monkeypatch.setattr(
        scraper, "_create_news_post", lambda **kwargs: created.update(kwargs)
    )

    scraper._scrape_single_research_article(
        article_url="https://news.example.org/articles/2",
        source_name="Configured Source",
        source=source,
    )

    assert created["title"] == "Heuristic Title"
    assert created["abstract"] == "Heuristic body with enough length."
    assert created["source_url"] == "https://news.example.org/articles/2"
    warning_mock.assert_not_called()
