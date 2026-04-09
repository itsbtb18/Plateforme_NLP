from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class TavilySearchClient:
    """Async wrapper around the official Tavily search client."""

    def __init__(self, api_key: str | None = None, **client_kwargs: Any) -> None:
        self.api_key = api_key or self._resolve_api_key()
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY is not configured")

        try:
            from tavily import TavilyClient
        except ImportError as exc:
            raise RuntimeError(
                "tavily-python is not installed. Install it with: pip install tavily-python"
            ) from exc

        self.client = TavilyClient(api_key=self.api_key, **client_kwargs)

    @staticmethod
    def _resolve_api_key() -> str:
        configured = getattr(settings, "TAVILY_API_KEY", "") or ""
        if configured.strip():
            return configured.strip()
        return os.environ.get("TAVILY_API_KEY", "").strip()

    async def _search(self, query: str, max_results: int = 15) -> list[dict]:
        """Search Tavily and return normalized items."""
        query_text = (query or "").strip()
        if not query_text:
            return []

        bounded_max_results = max(1, min(int(max_results), 50))

        try:
            response = await asyncio.to_thread(
                self.client.search,
                query=query_text,
                search_depth="advanced",
                max_results=bounded_max_results,
            )
        except Exception as exc:
            logger.warning(
                "Tavily search failed for query=%s error=%s",
                query_text,
                exc,
            )
            return []

        if not isinstance(response, dict):
            return []

        results = response.get("results") or []
        normalized_results: list[dict] = []

        for result in results:
            if not isinstance(result, dict):
                continue

            normalized_results.append(
                {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                }
            )

        return normalized_results

    async def search_events(self, query: str, max_results: int = 15) -> list[dict]:
        """Compatibility API for event scrapers."""
        return await self._search(query=query, max_results=max_results)

    async def search_web(self, query: str, max_results: int = 15) -> list[dict]:
        """Compatibility API used by tools/news/courses/corpus scrapers."""
        throttle_seconds = getattr(settings, "SCRAPING_API_CALL_DELAY_SECONDS", 0)
        try:
            delay_seconds = max(0.0, float(throttle_seconds))
        except (TypeError, ValueError):
            delay_seconds = 0.0
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
        return await self._search(query=query, max_results=max_results)


__all__ = ["TavilySearchClient"]
