"""Helpers to load scraping fixture data safely."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
_DEFAULT_SOURCES_PATH = _FIXTURE_DIR / "default_sources.json"
_CURATED_TOOLS_PATH = _FIXTURE_DIR / "curated_tools.json"
_CUSTOM_TAXONOMY_PATH = _FIXTURE_DIR / "custom_scraper_taxonomy.json"
_EVENT_TYPE_KEYWORDS_PATH = _FIXTURE_DIR / "event_type_keywords.json"


@lru_cache(maxsize=1)
def load_default_sources() -> list[dict[str, Any]]:
    """Return default source fixture entries."""
    try:
        data = json.loads(_DEFAULT_SOURCES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [entry for entry in data if isinstance(entry, dict)]


@lru_cache(maxsize=1)
def load_curated_tools() -> list[dict[str, Any]]:
    """Return curated tools fixture entries."""
    try:
        data = json.loads(_CURATED_TOOLS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [entry for entry in data if isinstance(entry, dict)]


@lru_cache(maxsize=1)
def load_custom_scraper_taxonomy() -> dict[str, Any]:
    """Return taxonomy mapping data used by the custom domain scraper."""
    try:
        data = json.loads(_CUSTOM_TAXONOMY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


@lru_cache(maxsize=1)
def load_event_type_keywords() -> dict[str, list[str]]:
    """Return event-type keyword mapping used by the event scraper."""
    if not _EVENT_TYPE_KEYWORDS_PATH.exists():
        logger.warning(
            "event_type_keywords_fixture_missing",
            extra={"path": str(_EVENT_TYPE_KEYWORDS_PATH)},
        )
        return {}

    try:
        data = json.loads(_EVENT_TYPE_KEYWORDS_PATH.read_text(encoding="utf-8"))
    except Exception:
        logger.warning(
            "event_type_keywords_fixture_unreadable",
            extra={"path": str(_EVENT_TYPE_KEYWORDS_PATH)},
        )
        return {}

    if not isinstance(data, dict):
        logger.warning(
            "event_type_keywords_fixture_invalid_type",
            extra={"path": str(_EVENT_TYPE_KEYWORDS_PATH)},
        )
        return {}

    normalized: dict[str, list[str]] = {}
    for event_type, keywords in data.items():
        if not isinstance(event_type, str) or not isinstance(keywords, list):
            continue
        normalized[event_type.strip().lower()] = [
            str(keyword).strip().lower() for keyword in keywords if str(keyword).strip()
        ]
    return normalized


def sources_for_section(section: str) -> list[dict[str, Any]]:
    """Filter default sources by section."""
    target = (section or "").strip().lower()
    if not target:
        return []
    return [
        row
        for row in load_default_sources()
        if str(row.get("section", "")).strip().lower() == target
    ]


def curated_tools_by_type(kind: str) -> list[dict[str, Any]]:
    """Filter curated tools by type (e.g. model, dataset)."""
    target = (kind or "").strip().lower()
    if not target:
        return []
    return [
        row
        for row in load_curated_tools()
        if str(row.get("type", "")).strip().lower() == target
    ]
