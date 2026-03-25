"""
Exa result cache — 24h TTL in-memory cache.

Cache key = hash(normalized_query + intent + language).
Stores URLs + extracted text + timestamp.
Deduplicates by URL + content hash when merging fresh results.
"""

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# In-memory cache store: key -> {docs, timestamp, urls_set}
_cache: Dict[str, Dict[str, Any]] = {}


def _make_key(query: str, intent: str, language: str) -> str:
    """Create a stable cache key from query + intent + language."""
    normalized = query.strip().lower()
    raw = f"{normalized}::{intent}::{language}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _content_hash(doc: Dict) -> str:
    """Create a hash of a doc's URL + first 500 chars of content."""
    url = doc.get("url", "")
    content = (doc.get("content", "") or "")[:500]
    return hashlib.md5(f"{url}::{content}".encode("utf-8")).hexdigest()


def cache_get(query: str, intent: str, language: str) -> Optional[List[Dict]]:
    """Return cached results if present and not expired, else None."""
    key = _make_key(query, intent, language)
    entry = _cache.get(key)
    if entry is None:
        logger.debug("Exa cache MISS: key=%s", key[:12])
        return None

    ttl_seconds = settings.EXA_CACHE_TTL_HOURS * 3600
    age = time.time() - entry["timestamp"]
    if age > ttl_seconds:
        logger.debug("Exa cache EXPIRED: key=%s age=%.0fs", key[:12], age)
        del _cache[key]
        return None

    logger.info(
        "Exa cache HIT: key=%s docs=%d age=%.0fs",
        key[:12], len(entry["docs"]), age,
    )
    return entry["docs"]


def cache_set(
    query: str,
    intent: str,
    language: str,
    docs: List[Dict],
) -> None:
    """Store results in cache, deduplicating by URL + content hash."""
    key = _make_key(query, intent, language)

    # Deduplicate incoming docs
    seen_hashes = set()
    unique_docs = []
    for doc in docs:
        h = _content_hash(doc)
        if h not in seen_hashes:
            seen_hashes.add(h)
            unique_docs.append(doc)

    _cache[key] = {
        "docs": unique_docs,
        "timestamp": time.time(),
        "hashes": seen_hashes,
    }

    logger.info(
        "Exa cache SET: key=%s docs=%d (dedup from %d)",
        key[:12], len(unique_docs), len(docs),
    )


def cache_clear() -> int:
    """Clear all cache entries. Returns count of entries cleared."""
    count = len(_cache)
    _cache.clear()
    return count


def cache_stats() -> Dict[str, Any]:
    """Return cache statistics."""
    now = time.time()
    ttl = settings.EXA_CACHE_TTL_HOURS * 3600
    active = sum(1 for e in _cache.values() if (now - e["timestamp"]) < ttl)
    return {
        "total_entries": len(_cache),
        "active_entries": active,
        "expired_entries": len(_cache) - active,
    }
