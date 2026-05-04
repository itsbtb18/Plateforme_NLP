from __future__ import annotations

import httpx
<<<<<<< HEAD
from fastapi import HTTPException
=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

from app.config import get_settings
from app.prompt_engine import PromptEngine
from app.providers.base import Provider


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self) -> None:
        settings = get_settings()
<<<<<<< HEAD
        self.api_keys = self._load_keys(settings.TS_GEMINI_API_KEYS) or ([settings.TS_GEMINI_API_KEY] if settings.TS_GEMINI_API_KEY else [])
        print(f"TS_DEBUG: GeminiProvider loaded {len(self.api_keys)} keys")

        self.model = settings.TS_GEMINI_MODEL
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.timeout_seconds = max(10.0, float(settings.TS_PROVIDER_HTTP_TIMEOUT_SECONDS))
        self._current_key_idx = 0

    def _load_keys(self, keys_str: str) -> list[str]:
        if not keys_str: return []
        return [k.strip() for k in keys_str.split(",") if k.strip()]

    def _get_api_key(self) -> str:
        if not self.api_keys:
            raise RuntimeError("TS_GEMINI_API_KEY is not configured")
        return self.api_keys[self._current_key_idx]

    def _rotate_key(self):
        if self.api_keys:
            self._current_key_idx = (self._current_key_idx + 1) % len(self.api_keys)
=======
        self.api_key = settings.TS_GEMINI_API_KEY
        self.model = settings.TS_GEMINI_MODEL
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

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

<<<<<<< HEAD
    async def chat(self, *, system_prompt: str, user_prompt: str, max_tokens: int = 2048) -> str:
        prompt = f"{system_prompt}\n\n{user_prompt}"
        return await self._generate(prompt, max_output_tokens=max_tokens)


    async def _generate(self, prompt: str, max_output_tokens: int | None = None) -> str:
        max_attempts = len(self.api_keys) or 1
        last_error = None

        for attempt in range(max_attempts):
            api_key = self._get_api_key()
            print(f"TS_DEBUG: Gemini attempt {attempt+1}/{max_attempts} with key ...{api_key[-5:]}")
            generation_config: dict[str, object] = {"temperature": 0.1}
            if max_output_tokens is not None:
                generation_config["maxOutputTokens"] = max_output_tokens

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": generation_config,
            }
            url = f"{self.base_url}/models/{self.model}:generateContent"
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(url, params={"key": api_key}, json=payload)
                    response.raise_for_status()
                    data = response.json()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if response.status_code == 429:
                    print(f"TS_DEBUG: Key ...{api_key[-5:]} rate limited (429)")
                    self._rotate_key()
                    continue
                print(f"TS_DEBUG: Key ...{api_key[-5:]} failed with {response.status_code}")
                raise
            except Exception as exc:
                last_error = exc
                print(f"TS_DEBUG: Key ...{api_key[-5:]} failed with {str(exc)}")
                raise

            candidates = data.get("candidates") or []
            if not candidates:
                print(f"TS_DEBUG: Key ...{api_key[-5:]} returned no candidates")
                return ""
            parts = (candidates[0].get("content") or {}).get("parts") or []
            return "\n".join(str(p.get("text", "")).strip() for p in parts if p.get("text")).strip()

        print(f"TS_DEBUG: All {max_attempts} keys in pool are exhausted (rate-limited)")
        raise HTTPException(
            status_code=429,
            detail=f"All {max_attempts} API keys in the rotation pool are currently rate-limited. Please wait 60s for quota reset or add more keys to TS_GEMINI_API_KEYS."
        )
=======
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
        async with httpx.AsyncClient(timeout=90.0) as client:
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
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

    @staticmethod
    def _translation_max_tokens(text: str) -> int:
        estimated = (len(text) // 3) + 900
        return max(1200, min(8192, estimated))
