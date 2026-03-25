from unittest.mock import MagicMock

import pytest
from defusedxml.common import DefusedXmlException

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
