from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.service import TranslationSummarizationService


class _FailingProvider:
    async def translate(self, **kwargs):
        raise RuntimeError("primary failed")

    async def summarize(self, **kwargs):
        raise RuntimeError("primary failed")


class _WorkingProvider:
    async def translate(self, **kwargs):
        return "fallback-translation"

    async def summarize(self, **kwargs):
        return "fallback-summary"


def test_provider_order_from_env(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "gemini")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "groq")

    from app.config import get_settings

    get_settings.cache_clear()
    svc = TranslationSummarizationService()
    assert svc.provider_order() == ["gemini", "groq"]


def test_translate_uses_fallback(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "gemini")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "groq")

    from app.config import get_settings

    get_settings.cache_clear()
    svc = TranslationSummarizationService()
    svc.providers = {"gemini": _FailingProvider(), "groq": _WorkingProvider()}

    output, provider, fallback = _run_async(
        svc.translate(text="bonjour", source_language="fr", target_language="en")
    )

    assert output == "fallback-translation"
    assert provider == "groq"
    assert fallback is True


def test_summarize_uses_primary(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "gemini")

    from app.config import get_settings

    get_settings.cache_clear()
    svc = TranslationSummarizationService()
    svc.providers = {"gemini": _FailingProvider(), "groq": _WorkingProvider()}

    output, provider, fallback = _run_async(
        svc.summarize(text="Long text", language="en", style="brief", max_words=120)
    )

    assert "fallback-summary" in output
    assert "# Document" in output
    assert provider == "groq"
    assert fallback is False


def _run_async(coro):
    import asyncio

    return asyncio.run(coro)
