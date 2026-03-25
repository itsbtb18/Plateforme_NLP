"""Unit tests for memory intent classification and memory retrieval.

Tests cover:
  - Classifier regex fast-path for memory intents (AR/FR/EN)
  - Regression: existing intents still classify correctly
"""
import sys
import os

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.classifier.engine import (
    _MEMORY_TRANSLATE_RE,
    _MEMORY_REPEAT_RE,
    _MEMORY_SUMMARIZE_RE,
    _MEMORY_COMPARE_RE,
    _GREETING_RE,
    _IDENTITY_RE,
)
from app.services.memory.memory_handler import extract_target_language


# ── Memory intent regex detection (EN) ────────────────────────────────


def test_translate_intent_en():
    assert _MEMORY_TRANSLATE_RE.search("translate my last question to english")
    assert _MEMORY_TRANSLATE_RE.search("translate the previous query to french")
    assert _MEMORY_TRANSLATE_RE.search("my last question translate to arabic")


def test_repeat_intent_en():
    assert _MEMORY_REPEAT_RE.search("what was my last question")
    assert _MEMORY_REPEAT_RE.search("repeat my previous question")
    assert _MEMORY_REPEAT_RE.search("show my last query")


def test_summarize_intent_en():
    assert _MEMORY_SUMMARIZE_RE.search("summarize your last answer")
    assert _MEMORY_SUMMARIZE_RE.search("summarise the previous response")
    assert _MEMORY_SUMMARIZE_RE.search("your last reply summarize")


def test_compare_intent_en():
    assert _MEMORY_COMPARE_RE.search("compare my last two questions")
    assert _MEMORY_COMPARE_RE.search("compare the last 2 queries")


# ── Memory intent regex detection (FR) ────────────────────────────────


def test_translate_intent_fr():
    assert _MEMORY_TRANSLATE_RE.search("traduis ma dernière question en anglais")
    assert _MEMORY_TRANSLATE_RE.search("traduit ma dernière requête en français")


def test_repeat_intent_fr():
    assert _MEMORY_REPEAT_RE.search("répète ma dernière question")
    assert _MEMORY_REPEAT_RE.search("répète ma derniere requête")


def test_summarize_intent_fr():
    assert _MEMORY_SUMMARIZE_RE.search("résume ta dernière réponse")
    assert _MEMORY_SUMMARIZE_RE.search("résumé la dernière réponse")


def test_compare_intent_fr():
    assert _MEMORY_COMPARE_RE.search("compare mes deux dernières questions")


# ── Memory intent regex detection (AR) ────────────────────────────────


def test_translate_intent_ar():
    assert _MEMORY_TRANSLATE_RE.search("ترجم آخر سؤال إلى الإنجليزية")
    assert _MEMORY_TRANSLATE_RE.search("ترجم سؤال الأخير")


def test_repeat_intent_ar():
    assert _MEMORY_REPEAT_RE.search("أعد آخر سؤال")
    assert _MEMORY_REPEAT_RE.search("كرر الأخير سؤال")


def test_summarize_intent_ar():
    assert _MEMORY_SUMMARIZE_RE.search("لخص آخر إجابة")
    assert _MEMORY_SUMMARIZE_RE.search("اختصر الأخيرة إجابة")


def test_compare_intent_ar():
    assert _MEMORY_COMPARE_RE.search("قارن آخر سؤالين")


# ── Target language extraction ────────────────────────────────────────


def test_extract_target_english():
    assert extract_target_language("translate to english") == "en"
    assert extract_target_language("traduis en anglais") == "en"
    assert extract_target_language("ترجم إلى الإنجليزية") == "en"


def test_extract_target_french():
    assert extract_target_language("translate to french") == "fr"
    assert extract_target_language("en français") == "fr"


def test_extract_target_arabic():
    assert extract_target_language("translate to arabic") == "ar"
    assert extract_target_language("إلى العربية") == "ar"


def test_extract_target_default():
    # Default to English if no target language detected
    assert extract_target_language("translate my last question") == "en"


# ── Regression: existing intents not broken ───────────────────────────


def test_greetings_still_work():
    assert _GREETING_RE.match("hello")
    assert _GREETING_RE.match("bonjour")
    assert _GREETING_RE.match("مرحبا")
    assert _GREETING_RE.match("السلام عليكم")


def test_identity_still_works():
    assert _IDENTITY_RE.search("who are you")
    assert _IDENTITY_RE.search("qui es-tu")
    assert _IDENTITY_RE.search("من أنت")


def test_memory_regex_does_not_match_normal_queries():
    normal_queries = [
        "What is NLP?",
        "Quelles sont les lois universitaires?",
        "ما هي إجراءات التسجيل؟",
        "find tools for arabic nlp",
        "who am I?",
        "hello",
    ]
    for q in normal_queries:
        assert not _MEMORY_TRANSLATE_RE.search(q), f"False positive on: {q}"
        assert not _MEMORY_REPEAT_RE.search(q), f"False positive on: {q}"
        assert not _MEMORY_SUMMARIZE_RE.search(q), f"False positive on: {q}"
        assert not _MEMORY_COMPARE_RE.search(q), f"False positive on: {q}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
