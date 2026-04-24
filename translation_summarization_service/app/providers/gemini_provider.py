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
        self.timeout_seconds = max(10.0, float(settings.TS_PROVIDER_HTTP_TIMEOUT_SECONDS))

    async def translate(self, *, text: str, source_language: str, target_language: str) -> str:
        prompt = PromptEngine.translation_prompt(
            text=text,
            source_language=source_language,
            target_language=target_language,
        )
        return await self._generate(
            prompt,
            max_output_tokens=self._translation_max_tokens(text),
        )

    async def summarize(self, *, text: str, language: str, style: str, max_words: int | None) -> str:
        prompt = PromptEngine.summarization_prompt(
            text=text,
            language=language,
            style=style,
            max_words=max_words,
        )
        return await self._generate(prompt, max_output_tokens=1536)

    async def _generate(self, prompt: str, max_output_tokens: int | None = None) -> str:
        if not self.api_key:
            raise RuntimeError("TS_GEMINI_API_KEY is not configured")

        generation_config: dict[str, object] = {"temperature": 0.1}
        if max_output_tokens is not None:
            generation_config["maxOutputTokens"] = max_output_tokens

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }
        url = f"{self.base_url}/models/{self.model}:generateContent"
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(url, params={"key": self.api_key}, json=payload)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        raise RuntimeError(f"Gemini rate limit (429). retry after {retry_after}") from exc
                    raise RuntimeError("Gemini rate limit (429)") from exc
                raise
            data = response.json()

        candidates = data.get("candidates") or []
        if not candidates:
            return ""
        parts = (candidates[0].get("content") or {}).get("parts") or []
        return "\n".join(str(p.get("text", "")).strip() for p in parts if p.get("text")).strip()

    @staticmethod
    def _translation_max_tokens(text: str) -> int:
        estimated = (len(text) // 3) + 900
        return max(1200, min(8192, estimated))
