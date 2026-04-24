from __future__ import annotations

from langdetect import LangDetectException, detect

from app.ai.provider_registry import get_provider_registry
from app.ai.providers.base import ModelDecision, Provider


class IntelligentModelRouter:
    """Groq-first router with Gemini fallback based on language/quality rules."""

    _WELL_SUPPORTED_BY_GROQ = {"ar", "en", "fr", "es", "de", "it", "pt"}

    @staticmethod
    def _normalize_language(language: str | None, sample_text: str | None) -> str:
        if language and str(language).strip():
            return str(language).strip().lower()[:2]
        if sample_text and sample_text.strip():
            try:
                return detect(sample_text).lower()[:2]
            except LangDetectException:
                return "unknown"
        return "unknown"

    async def choose_chain(
        self,
        *,
        task: str,
        language: str,
        domain: str | None,
        input_chars: int,
        sample_text: str | None = None,
        latency_budget_ms: int | None = None,
    ) -> list[tuple[Provider, ModelDecision]]:
        _ = domain
        normalized_language = self._normalize_language(language, sample_text)
        registry = get_provider_registry()

        groq = registry.get("groq-primary")
        gemini = registry.get("gemini-fallback")

        chain: list[tuple[Provider, ModelDecision]] = []

        if await groq.healthcheck():
            chain.append(
                (
                    groq,
                    ModelDecision(
                        provider_name=groq.name,
                        model_name="groq-primary",
                        estimated_cost_usd=groq.cost_estimate(input_chars=input_chars, task=task),
                        estimated_latency_ms=900,
                    ),
                )
            )

        if await gemini.healthcheck():
            latency = 1300 if normalized_language in self._WELL_SUPPORTED_BY_GROQ else 1100
            if latency_budget_ms and latency > latency_budget_ms:
                latency += 1000
            chain.append(
                (
                    gemini,
                    ModelDecision(
                        provider_name=gemini.name,
                        model_name="gemini-fallback",
                        estimated_cost_usd=gemini.cost_estimate(input_chars=input_chars, task=task),
                        estimated_latency_ms=latency,
                    ),
                )
            )

        if not chain:
            raise RuntimeError("No healthy AI providers available")

        # Rule: always try Groq first, then Gemini fallback.
        return chain

    async def choose(
        self,
        *,
        task: str,
        language: str,
        domain: str | None,
        input_chars: int,
        latency_budget_ms: int | None = None,
    ) -> tuple[Provider, ModelDecision]:
        chain = await self.choose_chain(
            task=task,
            language=language,
            domain=domain,
            input_chars=input_chars,
            sample_text=None,
            latency_budget_ms=latency_budget_ms,
        )
        return chain[0]


_router: IntelligentModelRouter | None = None


def get_model_router() -> IntelligentModelRouter:
    global _router
    if _router is None:
        _router = IntelligentModelRouter()
    return _router
