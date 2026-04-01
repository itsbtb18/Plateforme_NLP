"""Unit tests for card/entity explain fallback answers."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas import EntityExplainRequest
from app.services.chat_logic import build_entity_explain_fallback_answer


def test_entity_fallback_answer_english_contains_card_metadata():
    req = EntityExplainRequest(
        entity_type="institution",
        entity_title="Akcent International House Prague",
        entity_description="University active in NLP and computational linguistics.",
        entity_metadata={
            "category": "University",
            "author": "Akcent House",
            "url": "https://example.org/akcent",
        },
        session_id="s1",
    )

    answer = build_entity_explain_fallback_answer(req, "en")

    assert "Verified information about Akcent International House Prague:" in answer
    assert "- Type: institution" in answer
    assert "- Category: University" in answer
    assert "- Author/Owner: Akcent House" in answer
    assert "- Link: https://example.org/akcent" in answer


def test_entity_fallback_answer_arabic_header():
    req = EntityExplainRequest(
        entity_type="tool",
        entity_title="CAMeL Tools",
        entity_description="Arabic NLP toolkit",
        entity_metadata={},
        session_id="s2",
    )

    answer = build_entity_explain_fallback_answer(req, "ar")
    assert "معلومة مؤكدة حول CAMeL Tools:" in answer
