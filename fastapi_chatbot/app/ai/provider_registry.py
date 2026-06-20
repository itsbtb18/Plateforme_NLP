from __future__ import annotations

from app.ai.providers.base import Provider
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.groq_provider import GroqProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {
            "groq-primary": GroqProvider(),
            "gemini-fallback": GeminiProvider(),
        }

    def get(self, name: str) -> Provider:
        if name not in self._providers:
            raise KeyError(f"Provider not found: {name}")
        return self._providers[name]

    def all(self) -> list[Provider]:
        return list(self._providers.values())


_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry
