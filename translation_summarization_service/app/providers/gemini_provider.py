from __future__ import annotations

import httpx

from app.config import get_settings
from app.prompt_engine import PromptEngine
from app.providers.base import Provider


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.TS_GEMINI_API_KEY
        self.model = settings.TS_GEMINI_MODEL
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def translate(self, *, text: str, source_language: str, target_language: str) -> str:
        prompt = PromptEngine.translation_prompt(
            text=text,
            source_language=source_language,
            target_language=target_language,
        )
        return await self._generate(prompt)

    async def summarize(self, *, text: str, language: str, style: str, max_words: int | None) -> str:
        prompt = PromptEngine.summarization_prompt(
            text=text,
            language=language,
            style=style,
            max_words=max_words,
        )
        return await self._generate(prompt)

    async def _generate(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("TS_GEMINI_API_KEY is not configured")

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1},
        }
        url = f"{self.base_url}/models/{self.model}:generateContent"
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(url, params={"key": self.api_key}, json=payload)
            response.raise_for_status()
            data = response.json()

        candidates = data.get("candidates") or []
        if not candidates:
            return ""
        parts = (candidates[0].get("content") or {}).get("parts") or []
        return "\n".join(str(p.get("text", "")).strip() for p in parts if p.get("text")).strip()
