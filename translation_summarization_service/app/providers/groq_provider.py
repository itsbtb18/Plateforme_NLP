from __future__ import annotations

import asyncio

from groq import Groq
from groq.types.chat import ChatCompletion

from app.config import get_settings
from app.prompt_engine import PromptEngine
from app.providers.base import Provider


class GroqProvider(Provider):
    name = "groq"

    def __init__(self) -> None:
        settings = get_settings()
        self.api_keys = self._load_keys(settings.TS_GROQ_API_KEYS) or ([settings.TS_GROQ_API_KEY] if settings.TS_GROQ_API_KEY else [])
        self.model_translate = settings.TS_GROQ_TRANSLATION_MODEL
        self.model_summarize = settings.TS_GROQ_SUMMARIZATION_MODEL
        self.timeout_seconds = max(10.0, float(settings.TS_PROVIDER_HTTP_TIMEOUT_SECONDS))
        self._current_key_idx = 0

    def _load_keys(self, keys_str: str) -> list[str]:
        if not keys_str: return []
        return [k.strip() for k in keys_str.split(",") if k.strip()]

    def _get_client(self) -> Groq:
        if not self.api_keys:
            raise RuntimeError("TS_GROQ_API_KEY is not configured")
        key = self.api_keys[self._current_key_idx]
        return Groq(api_key=key, timeout=self.timeout_seconds, max_retries=0)

    def _rotate_key(self):
        if self.api_keys:
            self._current_key_idx = (self._current_key_idx + 1) % len(self.api_keys)

    async def translate(self, *, text: str, source_language: str, target_language: str) -> str:
        prompt = PromptEngine.translation_prompt(
            text=text,
            source_language=source_language,
            target_language=target_language,
        )
        return await self._chat(
            prompt=prompt,
            model=self.model_translate,
            max_tokens=self._translation_max_tokens(text),
        )

    async def summarize(self, *, text: str, language: str, style: str, max_words: int | None) -> str:
        prompt = PromptEngine.summarization_prompt(
            text=text,
            language=language,
            style=style,
            max_words=max_words,
        )
        return await self._chat(prompt=prompt, model=self.model_summarize, max_tokens=1024)

    async def _chat(self, *, prompt: str, model: str, max_tokens: int) -> str:
        max_attempts = len(self.api_keys) or 1
        last_error = None

        for attempt in range(max_attempts):
            client = self._get_client()
            try:
                def _run() -> str:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        max_tokens=max_tokens,
                        stream=False,
                    )
                    if not isinstance(response, ChatCompletion):
                        raise ValueError("Unexpected response type from Groq")
                    return (response.choices[0].message.content or "").strip()

                return await asyncio.to_thread(_run)
            except Exception as exc:
                last_error = exc
                if "rate_limit" in str(exc).lower() or "429" in str(exc):
                    self._rotate_key()
                    continue
                raise

        raise last_error or RuntimeError("Groq chat failed after rotation")

    @staticmethod
    def _translation_max_tokens(text: str) -> int:
        # Use a larger dynamic completion budget for full-document translation.
        estimated = (len(text) // 3) + 900
        return max(1200, min(8192, estimated))
