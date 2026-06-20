from __future__ import annotations

import httpx

from app.ai.providers.base import Provider
from app.config import get_settings

settings = get_settings()


class GeminiProvider(Provider):
    name = "gemini-fallback"

    def __init__(self) -> None:
        self.api_key = settings.GENAI_API_KEY
        self.model_translate = settings.GENAI_MODEL
        self.model_summarize = settings.GENAI_MODEL
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

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
        return await self._generate(prompt=prompt, model=self.model_translate)

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
        return await self._generate(prompt=prompt, model=self.model_summarize)

    async def healthcheck(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    params={"key": self.api_key},
                )
            return response.status_code < 500
        except Exception:
            return False

    def cost_estimate(self, *, input_chars: int, task: str) -> float:
        multiplier = 0.000018 if task == "translation" else 0.000022
        return round(input_chars * multiplier / 1000, 6)

    async def _generate(self, *, prompt: str, model: str) -> str:
        if not self.api_key:
            raise RuntimeError("GENAI_API_KEY is not configured")

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt,
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
            },
        }

        url = f"{self.base_url}/models/{model}:generateContent"
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(url, params={"key": self.api_key}, json=payload)
            response.raise_for_status()
            data = response.json()

        candidates = data.get("candidates") or []
        if not candidates:
            return ""
        parts = (candidates[0].get("content") or {}).get("parts") or []
        return "\n".join(str(p.get("text", "")).strip() for p in parts if p.get("text")).strip()
