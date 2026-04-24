from __future__ import annotations

import hashlib
import json
from typing import Any

from redis import Redis

from app.config import get_settings

settings = get_settings()


class AICache:
    def __init__(self) -> None:
        self.client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    @staticmethod
    def stable_hash(payload: dict[str, Any]) -> str:
        serialised = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialised.encode("utf-8")).hexdigest()

    def get_json(self, namespace: str, key: str) -> dict[str, Any] | None:
        raw = self.client.get(f"{namespace}:{key}")
        if not raw:
            return None
        return json.loads(raw)

    def set_json(self, namespace: str, key: str, value: dict[str, Any], ttl: int) -> None:
        self.client.setex(f"{namespace}:{key}", ttl, json.dumps(value, ensure_ascii=False))


_cache: AICache | None = None


def get_ai_cache() -> AICache:
    global _cache
    if _cache is None:
        _cache = AICache()
    return _cache
