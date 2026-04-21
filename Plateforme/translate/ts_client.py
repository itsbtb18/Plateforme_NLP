"""
Synchronous HTTP client for the Translation & Summarization micro-service.

Usage (inside a Django view):
    from translate.ts_client import ts_translate, ts_summarize

    translated = ts_translate("Bonjour le monde", "fr", "ar")
    summary    = ts_summarize(long_text, language="en", style="brief")
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT: int = getattr(settings, "TS_SERVICE_TIMEOUT", 120)


def _base_url() -> str:
    return getattr(settings, "TS_SERVICE_URL", "http://localhost:8010").rstrip("/")


def _headers() -> dict[str, str]:
    api_key = getattr(settings, "TS_SERVICE_API_KEY", "") or ""
    h: dict[str, str] = {"Content-Type": "application/json"}
    if api_key.strip():
        h["X-TS-Api-Key"] = api_key.strip()
    return h


def _post(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{_base_url()}{endpoint}"
    try:
        resp = requests.post(url, json=payload, headers=_headers(), timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.Timeout:
        logger.warning("TS service timeout: %s", url)
        raise RuntimeError("Translation/Summarization service timed out.")
    except requests.ConnectionError:
        logger.warning("TS service unreachable: %s", url)
        raise RuntimeError(
            "Translation/Summarization service is not reachable. "
            "Make sure it is running."
        )
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        detail = ""
        try:
            detail = exc.response.json().get("detail", str(exc))
        except Exception:
            detail = str(exc)
        logger.warning("TS service HTTP %s: %s", status, detail)
        raise RuntimeError(f"TS service error ({status}): {detail}")


# ── Public helpers ──────────────────────────────────────────────


def ts_translate(
    text: str,
    source_language: str,
    target_language: str,
) -> dict[str, Any]:
    """Translate *text* via the TS micro-service.

    Returns the full JSON response:
        {"task": "translation", "output": "...", "provider_used": "...", "fallback_used": false}
    """
    return _post(
        "/translate",
        {
            "text": text,
            "source_language": source_language,
            "target_language": target_language,
        },
    )


def ts_summarize(
    text: str,
    *,
    language: str = "en",
    style: str = "brief",
    max_words: int | None = None,
) -> dict[str, Any]:
    """Summarize *text* via the TS micro-service.

    Returns the full JSON response:
        {"task": "summarization", "output": "...", "provider_used": "...", "fallback_used": false}
    """
    payload: dict[str, Any] = {
        "text": text,
        "language": language,
        "style": style,
    }
    if max_words is not None:
        payload["max_words"] = max_words
    return _post("/summarize", payload)


def ts_health() -> dict[str, str]:
    """Quick health-check on the TS service."""
    url = f"{_base_url()}/health"
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
