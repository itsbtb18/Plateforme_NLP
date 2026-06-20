from __future__ import annotations

import asyncio

from groq import Groq
from groq.types.chat import ChatCompletion

from app.ai.providers.base import Provider
from app.config import get_settings

settings = get_settings()


class GroqProvider(Provider):
    name = "groq-primary"

    def __init__(self) -> None:
        self.api_key = settings.GROQ_API_KEY
        self.model_translate = settings.GROQ_MODEL
        self.model_summarize = settings.GROQ_MODEL
        self.client = Groq(api_key=self.api_key, timeout=15.0, max_retries=0) if self.api_key else None

    async def translate(
        self,
        *,
        text: str,
        source_language: str,
        target_language: str,
        glossary: dict[str, str] | None = None,
        preserve_named_entities: bool = True,
    ) -> str:
        glossary_text = "\n".join(f"- {k}: {v}" for k, v in (glossary or {}).items())
        preserve = "Preserve named entities exactly." if preserve_named_entities else ""
        prompt = (
            f"Translate from {source_language} to {target_language}.\n"
            f"{preserve}\n"
            f"Glossary:\n{glossary_text}\n\n"
            f"Text:\n{text}"
        )
        return await self._chat(prompt=prompt, model=self.model_translate)

    async def summarize(
        self,
        *,
        text: str,
        language: str,
        style: str,
        max_words: int | None,
        context_snippets: list[str] | None = None,
    ) -> str:
        context = "\n".join(context_snippets or [])
        prompt = (
            f"Summarize in {language}. Style={style}. Max words={max_words or 'auto'}.\n"
            "Ground every claim in the source context.\n"
            f"Context snippets:\n{context}\n\n"
            f"Source text:\n{text}"
        )
        return await self._chat(prompt=prompt, model=self.model_summarize)

    async def healthcheck(self) -> bool:
        if not self.client:
            return False

        def _check() -> bool:
            try:
                self.client.models.list()
                return True
            except Exception:
                return False

        return await asyncio.to_thread(_check)

    def cost_estimate(self, *, input_chars: int, task: str) -> float:
        multiplier = 0.000015 if task == "translation" else 0.00002
        return round(input_chars * multiplier / 1000, 6)

    async def _chat(self, *, prompt: str, model: str) -> str:
        if not self.client:
            raise RuntimeError("GROQ_API_KEY is not configured")

        def _run() -> str:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=settings.GROQ_MAX_TOKENS,
                stream=False,
            )
            if not isinstance(response, ChatCompletion):
                raise ValueError("Unexpected response type from Groq")
            return (response.choices[0].message.content or "").strip()

        return await asyncio.to_thread(_run)
