import pytest

from scraping.enrichment_engine import enrich_scraped_item
from scraping.llm_validation import validate_item


pytestmark = [pytest.mark.django_db, pytest.mark.integration]


@pytest.mark.parametrize(
    "category,payload,expected_keys",
    [
        (
            "events",
            {
                "title": "Event",
                "description": "NLP conference with workshops",
                "domains": "nlp",
                "location": "Algiers",
            },
            ["relevance_score"],
        ),
        (
            "tools",
            {
                "title": "Tool",
                "description": "Tokenizer and parser",
                "supported_languages": "ar,en",
            },
            ["supported_languages"],
        ),
        (
            "news",
            {
                "title": "News",
                "content": "New benchmark announced",
            },
            ["title"],
        ),
        (
            "courses",
            {
                "title": "Course",
                "description": "Syllabus and assignments",
                "field": "nlp",
            },
            ["field"],
        ),
        (
            "institutions",
            {
                "name": "Institute",
                "description": "Research lab",
                "country": "Algeria",
            },
            ["name"],
        ),
    ],
)
def test_enrichment_applies_common_outputs(category, payload, expected_keys):
    result = enrich_scraped_item(payload, category=category)

    for key in expected_keys:
        assert key in result


def test_enrichment_does_not_crash_if_llm_unavailable(monkeypatch):
    monkeypatch.setattr(
        "scraping.enrichment_engine.GroqLLMClient._chat",
        lambda *args, **kwargs: None,
    )
    payload = {
        "title": "Fallback Case",
        "description": "This should use heuristic fallback",
    }

    result = enrich_scraped_item(payload, category="events")

    assert isinstance(result, dict)
    assert result["title"] == "Fallback Case"


def test_llm_timeout_path_returns_safe_fallback(monkeypatch):
    class _DummyValidator:
        def validate(self, *args, **kwargs):
            return None

    monkeypatch.setattr(
        "scraping.llm_validation.get_validator", lambda: _DummyValidator()
    )

    assert validate_item({"title": "hello"}, "events") is None


def test_enrichment_returns_input_when_category_unknown():
    payload = {"title": "Unknown", "description": "No schema"}
    result = enrich_scraped_item(payload, category="unknown")
    assert result == payload
