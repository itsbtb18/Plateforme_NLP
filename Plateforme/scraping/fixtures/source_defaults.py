"""Normalized default source entries used by source seeding flows."""

from __future__ import annotations

from scraping.constants import CANONICAL_CATEGORIES
from scraping.fixture_loader import load_default_sources


def _normalize_category(entry: dict) -> str:
    return str(entry.get("category") or entry.get("section") or "").strip().lower()


def _normalize_trust_score(entry: dict) -> float:
    raw = entry.get("trust_score", 0.8)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 0.8
    return max(0.0, min(1.0, value))


def _build_default_sources() -> list[dict[str, object]]:
    allowed_categories = set(CANONICAL_CATEGORIES)
    seen: set[tuple[str, str]] = set()
    normalized: list[dict[str, object]] = []

    for entry in load_default_sources():
        category = _normalize_category(entry)
        if category not in allowed_categories:
            continue

        name = str(entry.get("name") or "").strip()
        url = str(entry.get("url") or "").strip()
        if not name or not url:
            continue

        key = (category, url.lower())
        if key in seen:
            continue
        seen.add(key)

        normalized.append(
            {
                "name": name,
                "url": url,
                "category": category,
                "trust_score": _normalize_trust_score(entry),
            }
        )

    return normalized


DEFAULT_SOURCES = _build_default_sources()
