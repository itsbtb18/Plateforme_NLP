import logging
from types import SimpleNamespace

from scraping.enrichment_engine import EnrichmentEngine
from scraping.scrapers.custom_scraper import CustomDomainScraper


def _base_tool_item():
    return {
        "title_en": "Arabic NLP Toolkit",
        "description_en": "A practical toolkit for Arabic NLP workflows.",
        "tool_type": "tokenization",
        "access_link": "https://example.com/tool",
    }


def test_enrichment_engine_happy_path_returns_enriched_payload(monkeypatch):
    class HappyClient:
        def _chat(self, system, user):
            return '{"title_ar": "عدة معالجة عربية", "description_ar": "وصف عربي واضح"}'

    import scraping.enrichment_engine as enrichment_engine

    monkeypatch.setattr(enrichment_engine, "GroqLLMClient", HappyClient)
    engine = EnrichmentEngine()

    enriched = engine.enrich_item(_base_tool_item(), "tools")

    assert enriched["title_ar"] == "عدة معالجة عربية"
    assert enriched["description_ar"] == "وصف عربي واضح"


def test_enrichment_engine_failure_logs_and_falls_back(monkeypatch, caplog):
    class FailingClient:
        def _chat(self, system, user):
            raise RuntimeError("boom")

    import scraping.enrichment_engine as enrichment_engine

    monkeypatch.setattr(enrichment_engine, "GroqLLMClient", FailingClient)
    engine = EnrichmentEngine()

    with caplog.at_level(logging.WARNING):
        enriched = engine.enrich_item(_base_tool_item(), "tools")

    # Graceful fallback: Arabic fields are backfilled from English
    assert enriched["title_ar"] == enriched["title_en"]
    assert enriched["description_ar"] == enriched["description_en"]

    log_messages = [r.getMessage() for r in caplog.records]
    assert any(
        "LLM call failed source=EnrichmentEngine._fill_translations" in msg
        for msg in log_messages
    )
    assert any("category=tools" in msg for msg in log_messages)
    assert any("exc_type=RuntimeError" in msg for msg in log_messages)
    assert any("message=boom" in msg for msg in log_messages)


def test_custom_scraper_llm_failure_logs_and_returns_empty(monkeypatch, caplog):
    class FailingClient:
        def _chat(self, system, user):
            raise RuntimeError("broken llm")

    import scraping.llm_validation as llm_validation

    monkeypatch.setattr(llm_validation, "GroqLLMClient", FailingClient)

    source = SimpleNamespace(
        category="news",
        use_rss=False,
        use_llm_extraction=True,
        base_url="https://example.com",
        name="Example Source",
        scrape_config={},
    )
    scraper = CustomDomainScraper(source)

    with caplog.at_level(logging.WARNING):
        items = scraper._extract_with_llm("Some page text")

    assert items == []
    assert any(
        e.get("type") == "llm_extraction_failed" for e in scraper.structured_errors
    )

    log_messages = [r.getMessage() for r in caplog.records]
    assert any(
        "LLM call failed source=https://example.com" in msg for msg in log_messages
    )
    assert any("category=news" in msg for msg in log_messages)
    assert any("exc_type=RuntimeError" in msg for msg in log_messages)
    assert any("message=broken llm" in msg for msg in log_messages)
