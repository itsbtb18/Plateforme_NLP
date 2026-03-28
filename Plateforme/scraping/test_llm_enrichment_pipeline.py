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
        def __init__(self, *args, **kwargs):
            pass

        def _chat(self, system, user):
            return '{"title_ar": "عدة معالجة عربية", "description_ar": "وصف عربي واضح"}'

    import scraping.enrichment_engine as enrichment_engine

    monkeypatch.setattr(enrichment_engine, "GroqLLMClient", HappyClient)
    engine = EnrichmentEngine()

    enriched = engine.enrich_item(_base_tool_item(), "tools")

    assert enriched["title_ar"] == "عدة معالجة عربية"
    assert enriched["description_ar"] == "وصف عربي واضح"


def test_enrichment_engine_failure_logs_and_falls_back(monkeypatch):
    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        def _chat(self, system, user):
            raise RuntimeError("boom")

    import scraping.enrichment_engine as enrichment_engine

    monkeypatch.setattr(enrichment_engine, "GroqLLMClient", FailingClient)
    engine = EnrichmentEngine()

    enriched = engine.enrich_item(_base_tool_item(), "tools")

    # Graceful fallback: Arabic fields are backfilled from English
    assert enriched["title_ar"] == enriched["title_en"]
    assert enriched["description_ar"] == enriched["description_en"]


def test_enrichment_engine_groq_init_failure_falls_back(monkeypatch):
    class BrokenClient:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("groq unavailable")

    import scraping.enrichment_engine as enrichment_engine

    monkeypatch.setattr(enrichment_engine, "GroqLLMClient", BrokenClient)
    engine = EnrichmentEngine()

    enriched = engine.enrich_item(_base_tool_item(), "tools")

    assert enriched["title_ar"] == enriched["title_en"]
    assert enriched["description_ar"] == enriched["description_en"]


def test_enrichment_engine_spacy_model_missing_uses_regex_fallback(monkeypatch):
    class NoLLMClient:
        def __init__(self, *args, **kwargs):
            pass

        def _chat(self, system, user):
            return None

    import scraping.enrichment_engine as enrichment_engine

    monkeypatch.setattr(enrichment_engine, "GroqLLMClient", NoLLMClient)
    monkeypatch.setattr(enrichment_engine, "_NLP", None)
    monkeypatch.setattr(enrichment_engine, "_NLP_AR", None)

    engine = EnrichmentEngine()
    keywords = engine._extract_keywords(
        "Arabic NLP tokenization pipeline for low-resource dialect processing",
        max_keywords=5,
    )

    assert isinstance(keywords, list)
    assert len(keywords) > 0


def test_extract_named_entities_with_spacy_loaded(monkeypatch):
    class FakeNLP:
        max_length = 100_000

        def __call__(self, text):
            return SimpleNamespace(
                ents=[
                    SimpleNamespace(text="Ahmed", label_="PERSON"),
                    SimpleNamespace(text="University of Algiers", label_="ORG"),
                    SimpleNamespace(text="Algiers", label_="GPE"),
                    SimpleNamespace(text="2026", label_="DATE"),
                    SimpleNamespace(text="BERT", label_="PRODUCT"),
                    SimpleNamespace(text="NLP Summit", label_="EVENT"),
                ]
            )

    import scraping.enrichment_engine as enrichment_engine

    monkeypatch.setattr(enrichment_engine, "_NLP", FakeNLP())
    monkeypatch.setattr(enrichment_engine, "_NLP_AR", FakeNLP())

    entities = enrichment_engine.extract_named_entities(
        "Ahmed from University of Algiers presented BERT at NLP Summit in Algiers in 2026."
    )

    assert entities["PERSON"] == ["Ahmed"]
    assert entities["ORG"] == ["University of Algiers"]
    assert entities["GPE"] == ["Algiers"]
    assert entities["DATE"] == ["2026"]
    assert entities["TECH"] == ["BERT"]
    assert entities["EVENT"] == ["NLP Summit"]


def test_extract_named_entities_uses_arabic_model(monkeypatch):
    class FakeNLP:
        max_length = 100_000

        def __init__(self, marker):
            self.marker = marker
            self.calls = 0

        def __call__(self, text):
            self.calls += 1
            return SimpleNamespace(
                ents=[SimpleNamespace(text=self.marker, label_="ORG")]
            )

    import scraping.enrichment_engine as enrichment_engine

    default_nlp = FakeNLP("DEFAULT")
    arabic_nlp = FakeNLP("ARABIC")
    monkeypatch.setattr(enrichment_engine, "_NLP", default_nlp)
    monkeypatch.setattr(enrichment_engine, "_NLP_AR", arabic_nlp)

    entities = enrichment_engine.extract_named_entities(
        "جامعة الجزائر", detected_language="ar"
    )

    assert entities["ORG"] == ["ARABIC"]
    assert arabic_nlp.calls == 1
    assert default_nlp.calls == 0


def test_extract_named_entities_returns_empty_when_spacy_missing(monkeypatch):
    import scraping.enrichment_engine as enrichment_engine

    monkeypatch.setattr(enrichment_engine, "_NLP", None)
    monkeypatch.setattr(enrichment_engine, "_NLP_AR", None)

    entities = enrichment_engine.extract_named_entities(
        "Arabic NLP at University of Algiers", detected_language="en"
    )

    assert entities == {}


def test_enrichment_engine_attaches_entities_to_item(monkeypatch):
    class HappyClient:
        def __init__(self, *args, **kwargs):
            pass

        def _chat(self, system, user):
            return '{"title_ar": "عدة معالجة عربية", "description_ar": "وصف عربي واضح"}'

    import scraping.enrichment_engine as enrichment_engine

    monkeypatch.setattr(enrichment_engine, "GroqLLMClient", HappyClient)
    monkeypatch.setattr(
        enrichment_engine,
        "extract_named_entities",
        lambda text, detected_language="en": {"ORG": ["Arabic NLP Toolkit"]},
    )

    engine = EnrichmentEngine()
    enriched = engine.enrich_item(_base_tool_item(), "tools")

    assert enriched["entities"] == {"ORG": ["Arabic NLP Toolkit"]}


def test_custom_scraper_llm_failure_logs_and_returns_empty(monkeypatch):
    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

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

    items = scraper._extract_with_llm("Some page text", "news")

    assert items == []
    assert any(
        e.get("type") == "llm_extraction_failed" for e in scraper.structured_errors
    )
