"""Lightweight enrichment engine with stdlib-only network behavior."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from django.utils import timezone

from scraping.extractors.core.llm_validation import GroqLLMClient

logger = logging.getLogger(__name__)

# Backward-compatible hooks used by enrichment tests that monkeypatch spaCy models.
_NLP = None
_NLP_AR = None


_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"https?://[^\s]+")


def extract_named_entities(
    text: str,
    detected_language: str = "en",
) -> dict[str, list[str]]:
    """Best-effort entity extraction using optional NLP models."""
    if not isinstance(text, str):
        return {}

    cleaned = text.strip()
    if not cleaned:
        return {}

    nlp_model = _NLP_AR if detected_language.startswith("ar") and _NLP_AR else _NLP
    if nlp_model is None:
        return {}

    try:
        doc = nlp_model(cleaned)
    except Exception:
        logger.debug("named_entity_extraction_failed", exc_info=True)
        return {}

    mapped: dict[str, set[str]] = {}
    label_map = {
        "PRODUCT": "TECH",
        "TECH": "TECH",
    }
    allowed = {"PERSON", "ORG", "GPE", "DATE", "EVENT", "TECH"}

    for ent in getattr(doc, "ents", []) or []:
        raw_text = str(getattr(ent, "text", "") or "").strip()
        raw_label = str(getattr(ent, "label_", "") or "").strip().upper()
        if not raw_text:
            continue
        normalized_label = label_map.get(raw_label, raw_label)
        if normalized_label not in allowed:
            continue
        mapped.setdefault(normalized_label, set()).add(raw_text)

    if mapped:
        return {label: sorted(values) for label, values in mapped.items()}

    entities: dict[str, list[str]] = {}

    emails = sorted(set(_EMAIL_RE.findall(cleaned)))
    if emails:
        entities["CONTACT"] = emails

    urls = sorted(set(_URL_RE.findall(cleaned)))
    if urls:
        entities["URL"] = urls

    if detected_language.startswith("ar"):
        arabic_tokens = [token for token in cleaned.split() if _ARABIC_RE.search(token)]
        if arabic_tokens:
            entities["ARABIC_TOKENS"] = sorted(set(arabic_tokens[:20]))
    else:
        capitalized = [
            token.strip(".,;:!?()[]{}\"'")
            for token in cleaned.split()
            if token[:1].isupper() and len(token) > 2
        ]
        if capitalized:
            entities["NOUN_PHRASES"] = sorted(set(capitalized[:30]))

    return entities


class EnrichmentEngine:
    """Small enrichment pipeline that is safe when LLM is unavailable."""

    def __init__(self):
        try:
            self.client = GroqLLMClient()
        except Exception as exc:
            logger.warning("Failed to initialize Groq client for enrichment: %s", exc)
            self.client = None

    def enrich_item(self, item: dict[str, Any], category: str) -> dict[str, Any]:
        if not isinstance(item, dict):
            return item

        payload = dict(item)
        normalized_category = (category or "").strip().lower() or "events"

        title = self._safe_text(payload.get("title_en") or payload.get("title"))
        description = self._safe_text(
            payload.get("description_en") or payload.get("description")
        )

        payload.setdefault("title", title)
        payload.setdefault("title_en", title)
        payload.setdefault("title_ar", payload.get("title_ar") or title)

        payload.setdefault("description", description)
        payload.setdefault("description_en", description)
        payload.setdefault(
            "description_ar", payload.get("description_ar") or description
        )

        detected_language = self._detect_language(
            f"{payload.get('title_en', '')} {payload.get('description_en', '')}"
        )
        payload.setdefault("language", detected_language)

        entity_text = " ".join(
            [
                self._safe_text(payload.get("title_en")),
                self._safe_text(payload.get("description_en")),
                self._safe_text(payload.get("source_url")),
            ]
        )
        payload["entities"] = extract_named_entities(entity_text, detected_language)

        if self.client and getattr(self.client, "is_configured", True):
            payload = self._apply_llm_enrichment(payload, normalized_category)

        payload.setdefault("enrichment_status", "complete")
        payload.setdefault("enriched_at", timezone.now().isoformat())

        return payload

    def _apply_llm_enrichment(
        self, payload: dict[str, Any], category: str
    ) -> dict[str, Any]:
        prompt = (
            "Improve the following JSON item for NLP curation. "
            "Return JSON only with corrected title_en, description_en, tags, and summary."
        )
        user_payload = json.dumps(
            {
                "category": category,
                "item": payload,
            },
            ensure_ascii=False,
        )
        try:
            raw = self.client._chat(prompt, user_payload)
            if not raw:
                return payload
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                return payload

            merged = dict(payload)
            for key in ("title_en", "description_en", "title_ar", "description_ar"):
                value = parsed.get(key)
                if isinstance(value, str) and value.strip():
                    merged[key] = value.strip()

            tags = parsed.get("tags")
            if isinstance(tags, list):
                merged["tags"] = [
                    str(tag).strip().lower() for tag in tags if str(tag).strip()
                ]

            summary = parsed.get("summary")
            if isinstance(summary, str) and summary.strip():
                merged["summary"] = summary.strip()

            merged["llm_enrichment"] = "applied"
            return merged
        except Exception as exc:
            logger.debug("llm_enrichment_failed error=%s", exc)
            payload["llm_enrichment"] = "failed"
            return payload

    @staticmethod
    def _safe_text(value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        return "" if text.lower() == "null" else text

    @staticmethod
    def _detect_language(text: str) -> str:
        blob = text or ""
        if _ARABIC_RE.search(blob):
            return "ar"
        lowered = blob.lower()
        if any(token in lowered for token in (" le ", " la ", " de ", " des ", " et ")):
            return "fr"
        return "en"

    @staticmethod
    def _extract_keywords(text: str, max_keywords: int = 10) -> list[str]:
        if not isinstance(text, str):
            return []
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
        seen: list[str] = []
        for token in tokens:
            if token in seen:
                continue
            seen.append(token)
            if len(seen) >= max(1, int(max_keywords or 10)):
                break
        return seen


def enrich_scraped_item(item, category):
    engine = EnrichmentEngine()
    return engine.enrich_item(item, category)
