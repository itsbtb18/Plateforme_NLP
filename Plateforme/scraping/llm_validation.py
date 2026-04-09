"""Lightweight LLM validation helpers for scraping."""

from __future__ import annotations

import json
import logging
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are an Arabic NLP curation assistant. Return JSON only with concise fields."
)

USER_PROMPT_TEMPLATE = """Category: {category}\n\nItem:\n{item_json}\n\nReturn JSON."""

CUSTOM_EXTRACTION_INSTRUCTIONS = {
    "events": "Extract event title, date, location, and URL.",
    "tools": "Extract tool name, purpose, URL, and language support.",
    "courses": "Extract course title, instructor, level, and enrollment URL.",
}


def build_custom_extraction_prompt(category: str, page_text: str) -> tuple[str, str]:
    normalized_category = (category or "").strip().lower()
    instruction = CUSTOM_EXTRACTION_INSTRUCTIONS.get(
        normalized_category,
        CUSTOM_EXTRACTION_INSTRUCTIONS["events"],
    )
    system_prompt = (
        "You are a strict extraction assistant for Arabic NLP curation. "
        "Return only a valid JSON array."
    )
    user_prompt = (
        f"Category: {normalized_category or 'events'}\n\n"
        f"Task: {instruction}\n\n"
        "Output format: JSON array only.\n\n"
        f"Webpage text:\n{page_text}"
    )
    return system_prompt, user_prompt


class GroqLLMClient:
    """Small Groq chat-completions client using urllib only."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
    ):
        self.api_key = api_key or getattr(settings, "GROQ_SCRAPING_API_KEY", "")
        self.model = model or getattr(
            settings, "GROQ_SCRAPING_MODEL", "llama-3.3-70b-versatile"
        )
        configured_timeout = timeout or getattr(settings, "GROQ_SCRAPING_TIMEOUT", 30)
        self.timeout = max(1, min(int(configured_timeout), 30))
        self.max_retries = max_retries or int(
            getattr(settings, "GROQ_SCRAPING_MAX_RETRIES", 1)
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _chat(self, system: str, user: str) -> str | None:
        if not self.is_configured:
            return None

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.15,
            "max_tokens": 2048,
        }
        raw_payload = json.dumps(payload).encode("utf-8")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        attempts = max(1, self.max_retries + 1)
        for attempt in range(attempts):
            request = Request(
                GROQ_CHAT_URL,
                data=raw_payload,
                method="POST",
                headers=headers,
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    body = response.read().decode("utf-8", errors="replace")
                parsed = json.loads(body)
                choices = parsed.get("choices") or []
                if not choices:
                    return None
                message = choices[0].get("message") or {}
                content = message.get("content")
                return content if isinstance(content, str) and content.strip() else None
            except HTTPError as exc:
                if attempt < attempts - 1 and int(exc.code) in {
                    429,
                    500,
                    502,
                    503,
                    504,
                }:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                logger.warning("Groq HTTP error: %s", exc)
                return None
            except (URLError, TimeoutError) as exc:
                if attempt < attempts - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                logger.warning("Groq network error: %s", exc)
                return None
            except Exception as exc:
                logger.warning("Groq response parse failed: %s", exc)
                return None

        return None


class LLMValidator:
    """Compatibility wrapper that enriches item payloads when LLM is configured."""

    def __init__(self, client: GroqLLMClient | None = None):
        self.client = client or GroqLLMClient()

    @property
    def is_available(self) -> bool:
        return bool(self.client.is_configured)

    def validate(
        self, item: dict[str, Any], category: str = "events"
    ) -> dict[str, Any]:
        payload = dict(item or {})
        if not self.is_available:
            payload.setdefault("llm_validation", "skipped")
            return payload

        prompt = USER_PROMPT_TEMPLATE.format(
            category=category,
            item_json=json.dumps(payload, ensure_ascii=False),
        )
        raw = self.client._chat(SYSTEM_PROMPT, prompt)
        if not raw:
            payload.setdefault("llm_validation", "no_response")
            return payload

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                payload.update(parsed)
                payload["llm_validation"] = "ok"
                return payload
        except Exception:
            logger.debug("llm_validation_json_parse_failed", exc_info=True)

        payload.setdefault("llm_validation", "invalid_json")
        return payload


_default_validator: LLMValidator | None = None


def get_validator() -> LLMValidator:
    global _default_validator
    if _default_validator is None:
        _default_validator = LLMValidator()
    return _default_validator


def validate_item(item: dict[str, Any], category: str = "events") -> dict[str, Any]:
    return get_validator().validate(item, category)
