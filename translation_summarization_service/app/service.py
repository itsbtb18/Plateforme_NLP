from __future__ import annotations

from app.config import get_settings
from app.providers.gemini_provider import GeminiProvider
from app.providers.groq_provider import GroqProvider


class TranslationSummarizationService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.providers = {
            "gemini": GeminiProvider(),
            "groq": GroqProvider(),
        }

    def provider_order(self) -> list[str]:
        primary = self.settings.TS_PRIMARY_PROVIDER.strip().lower()
        fallback = self.settings.TS_FALLBACK_PROVIDER.strip().lower()

        valid = {"gemini", "groq"}
        if primary not in valid:
            primary = "gemini"
        if fallback not in valid or fallback == primary:
            fallback = "groq" if primary == "gemini" else "gemini"

        return [primary, fallback]

    async def translate(self, *, text: str, source_language: str, target_language: str) -> tuple[str, str, bool]:
        errors: list[str] = []
        order = self.provider_order()
        for idx, name in enumerate(order):
            provider = self.providers[name]
            try:
                output = await provider.translate(
                    text=text,
                    source_language=source_language,
                    target_language=target_language,
                )
                return output, name, idx > 0
            except Exception as exc:
                errors.append(f"{name}: {exc}")
                continue
        raise RuntimeError("All providers failed: " + " | ".join(errors))

    async def summarize(self, *, text: str, language: str, style: str, max_words: int | None) -> tuple[str, str, bool]:
        errors: list[str] = []
        order = self.provider_order()
        for idx, name in enumerate(order):
            provider = self.providers[name]
            try:
                output = await provider.summarize(
                    text=text,
                    language=language,
                    style=style,
                    max_words=max_words,
                )
                return output, name, idx > 0
            except Exception as exc:
                errors.append(f"{name}: {exc}")
                continue
        raise RuntimeError("All providers failed: " + " | ".join(errors))
