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
        self.api_key = settings.TS_GROQ_API_KEY
        self.model_translate = settings.TS_GROQ_TRANSLATION_MODEL
        self.model_summarize = settings.TS_GROQ_SUMMARIZATION_MODEL
        self.client = Groq(api_key=self.api_key, timeout=15.0, max_retries=0) if self.api_key else None

    async def translate(self, *, text: str, source_language: str, target_language: str) -> str:
        prompt = PromptEngine.translation_prompt(
            text=text,
            source_language=source_language,
            target_language=target_language,
        )
        return await self._chat(prompt=prompt, model=self.model_translate, max_tokens=768)

    async def summarize(self, *, text: str, language: str, style: str, max_words: int | None) -> str:
        prompt = PromptEngine.summarization_prompt(
            text=text,
            language=language,
            style=style,
            max_words=max_words,
        )
        return await self._chat(prompt=prompt, model=self.model_summarize, max_tokens=1024)

    async def _chat(self, *, prompt: str, model: str, max_tokens: int) -> str:
        if not self.client:
            raise RuntimeError("TS_GROQ_API_KEY is not configured")

        def _run() -> str:
            response = self.client.chat.completions.create(
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
