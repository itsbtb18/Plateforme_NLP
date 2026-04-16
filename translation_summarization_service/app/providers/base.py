from __future__ import annotations

from abc import ABC, abstractmethod


class Provider(ABC):
    name: str

    @abstractmethod
    async def translate(self, *, text: str, source_language: str, target_language: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def summarize(self, *, text: str, language: str, style: str, max_words: int | None) -> str:
        raise NotImplementedError
