from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ModelDecision:
    provider_name: str
    model_name: str
    estimated_cost_usd: float
    estimated_latency_ms: int


class Provider(ABC):
    name: str

    @abstractmethod
    async def translate(
        self,
        *,
        text: str,
        source_language: str,
        target_language: str,
        glossary: dict[str, str] | None = None,
        preserve_named_entities: bool = True,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def summarize(
        self,
        *,
        text: str,
        language: str,
        style: str,
        max_words: int | None,
        context_snippets: list[str] | None = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def healthcheck(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def cost_estimate(self, *, input_chars: int, task: str) -> float:
        raise NotImplementedError
