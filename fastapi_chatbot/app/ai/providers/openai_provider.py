from __future__ import annotations

import httpx

from app.ai.providers.base import Provider
from app.config import get_settings

settings = get_settings()


class OpenAICompatibleProvider(Provider):
    name = "openai-compatible"

    def __init__(self) -> None:
        self.base_url = settings.AI_OPENAI_BASE_URL.rstrip("/")
        self.api_key = settings.AI_OPENAI_API_KEY
        self.model_translate = settings.AI_OPENAI_TRANSLATION_MODEL
        self.model_summarize = settings.AI_OPENAI_SUMMARY_MODEL

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
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
            return response.status_code < 500
        except Exception:
            return False

    def cost_estimate(self, *, input_chars: int, task: str) -> float:
        multiplier = 0.00002 if task == "translation" else 0.00003
        return round(input_chars * multiplier / 1000, 6)

    async def _chat(self, *, prompt: str, model: str) -> str:
        if not self.api_key:
            raise RuntimeError("AI_OPENAI_API_KEY is not configured")

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"].strip()
