from __future__ import annotations

import httpx

from app.ai.providers.base import Provider
from app.config import get_settings

settings = get_settings()


class LocalModelProvider(Provider):
    name = "local-vllm-ollama"

    def __init__(self) -> None:
        self.endpoint = settings.AI_LOCAL_PROVIDER_URL.rstrip("/")
        self.translate_model = settings.AI_LOCAL_TRANSLATION_MODEL
        self.summary_model = settings.AI_LOCAL_SUMMARY_MODEL

    async def translate(
        self,
        *,
        text: str,
        source_language: str,
        target_language: str,
        glossary: dict[str, str] | None = None,
        preserve_named_entities: bool = True,
    ) -> str:
        prompt = (
            f"Translate from {source_language} to {target_language}.\n"
            f"Preserve named entities={preserve_named_entities}.\n"
            f"Glossary={glossary or {}}\n\n{text}"
        )
        return await self._generate(self.translate_model, prompt)

    async def summarize(
        self,
        *,
        text: str,
        language: str,
        style: str,
        max_words: int | None,
        context_snippets: list[str] | None = None,
    ) -> str:
        prompt = (
            f"Summarize in {language}, style={style}, max_words={max_words or 'auto'}.\n"
            f"Context: {' '.join(context_snippets or [])}\n\n"
            f"{text}"
        )
        return await self._generate(self.summary_model, prompt)

    async def healthcheck(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.endpoint}/health")
            return response.status_code == 200
        except Exception:
            return False

    def cost_estimate(self, *, input_chars: int, task: str) -> float:
        _ = (input_chars, task)
        return 0.0

    async def _generate(self, model: str, prompt: str) -> str:
        payload = {"model": model, "prompt": prompt, "temperature": 0.1}
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.endpoint}/generate", json=payload)
            response.raise_for_status()
            data = response.json()
        return str(data.get("text", "")).strip()
