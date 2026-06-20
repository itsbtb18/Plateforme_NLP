from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from django.conf import settings
from scraping.api_key_manager import api_key_manager

logger = logging.getLogger(__name__)

def _get_direct_scraper():
    """Lazy import to avoid circular dependencies."""
    from scraping.scrapers.direct_source_scraper import DirectSourceScraper
    return DirectSourceScraper()


class TavilySearchClient:
    """Async wrapper around the official Tavily search client."""

    def __init__(self, api_key: str | None = None, **client_kwargs: Any) -> None:
        self.client = None
        self._client_kwargs = client_kwargs
        self._disabled_reason = ""
        self._disabled_logged = False

        self.api_keys = api_key_manager.providers.get("tavily", [])
        if api_key:
            self.api_keys.insert(0, api_key)
            
        if not self.api_keys:
            self._disabled_reason = "No Tavily API keys configured"
            return

        try:
            from tavily import TavilyClient
        except ImportError as exc:
            raise RuntimeError(
                "tavily-python is not installed. Install it with: pip install tavily-python"
            ) from exc

        current_key = api_key_manager.get_current_key("tavily")
        if not current_key and self.api_keys:
            current_key = self.api_keys[0]

        self.client = TavilyClient(
            api_key=current_key, **self._client_kwargs
        )

    @property
    def is_enabled(self) -> bool:
        return self.client is not None

    @property
    def disabled_reason(self) -> str:
        return self._disabled_reason


    async def _search(
        self,
        query: str,
        config: dict[str, Any],
        *,
        max_results: int | None = None,
    ) -> list[dict]:
        """Search Tavily with per-category configuration and return normalized items."""
        from scraping.scrapers.circuit_breaker import llm_circuit_breaker
        if llm_circuit_breaker.skip_tavily_if_all_down():
            logger.warning("Tavily skippé : tous les LLM en quarantaine")
            return []

        if self.client is None:
            if not self._disabled_logged:
                logger.info(
                    "Tavily search disabled: %s",
                    self._disabled_reason or "client unavailable",
                )
                self._disabled_logged = True
            return []

        query_text = (query or "").strip()
        if not query_text:
            return []

        request_config = dict(config or {})
        configured_max_results = request_config.get("max_results", 10)
        effective_max_results = max_results
        if effective_max_results is None:
            effective_max_results = configured_max_results

        try:
            request_config["max_results"] = max(1, min(int(effective_max_results), 50))
        except (TypeError, ValueError):
            request_config["max_results"] = 10

        try:
            response = await asyncio.to_thread(
                self.client.search,
                query=query_text,
                **request_config,
            )
        except Exception as exc:
            message = str(exc)
            lowered = message.lower()
            if (
                "usage limit" in lowered
                or "exceeds your plan" in lowered
                or "quota" in lowered
                or "429" in lowered
            ):
                new_key = api_key_manager.rotate_key("tavily", reason="usage_limit")
                if new_key:
                    logger.warning("Tavily API key exhausted. Rotating to next key...")
                    from tavily import TavilyClient
                    self.client = TavilyClient(api_key=new_key, **self._client_kwargs)
                    try:
                        response = await asyncio.to_thread(
                            self.client.search,
                            query=query_text,
                            **request_config,
                        )
                    except Exception as retry_exc:
                        logger.error("Tavily search failed with rotated key: %s", retry_exc)
                        return []
                else:
                    self._disabled_reason = "All Tavily keys exhausted"
                    self.client = None
                    return []
            else:
                logger.error("Tavily search failed: %s", exc)
                return []

        if not isinstance(response, dict):
            return []

        results = response.get("results", [])
        if not isinstance(results, list):
            return []

        filtered: list[dict] = []
        for raw_item in results:
            if not isinstance(raw_item, dict):
                continue
            title = str(raw_item.get("title") or "").strip()
            url = str(raw_item.get("url") or "").strip()
            content = str(raw_item.get("content") or "").strip()
            # Keep thin snippets (or even empty snippets) as long as URL+title exist.
            # The LLM can still infer structure from title/url context.
            if not content and not (title and url):
                continue
            filtered.append(
                {
                    "title": title,
                    "url": url,
                    "content": content,
                    "score": raw_item.get("score"),
                    "raw_content": raw_item.get("raw_content"),
                }
            )

        answer = response.get("answer")
        if isinstance(answer, str) and answer.strip():
            filtered.insert(
                0,
                {
                    "title": f"AI Summary: {query_text}",
                    "url": "tavily://answer",
                    "content": answer.strip(),
                    "score": 1.0,
                    "is_tavily_answer": True,
                },
            )

        return filtered

    async def search_events(
        self,
        query: str,
        max_results: int | None = None,
    ) -> list[dict]:
        """Override: Use DirectSourceScraper instead of Tavily for events."""
        logger.info("SearchClient: Using DirectSourceScraper for events (Tavily bypass)")
        scraper = _get_direct_scraper()
        return await scraper.scrape_events()

    async def search_tools(
        self,
        query: str,
        max_results: int | None = None,
    ) -> list[dict]:
        return await self._search(
            query,
            config={
                "search_depth": "advanced",
                "max_results": 8,
                "include_answer": True,
                "include_raw_content": True,
                "include_domains": [
                    "github.com",
                    "huggingface.co",
                    "pypi.org",
                    "npmjs.com",
                    "paperswithcode.com",
                    "camel-lab.github.io",
                    "farasa.qcri.org",
                    "sourceforge.net",
                    "bitbucket.org",
                    "gitlab.com",
                    "crane.io",
                ],
            },
            max_results=max_results,
        )

    async def search_courses(
        self,
        query: str,
        max_results: int | None = None,
    ) -> list[dict]:
        return await self._search(
            query,
            config={
                "search_depth": "advanced",
                "max_results": 10,
                "include_domains": [
                    "coursera.org",
                    "edx.org",
                    "udemy.com",
                    "youtube.com",
                    "mooc.org",
                    "futurelearn.com",
                    "datacamp.com",
                    "linkedin.com/learning",
                    "khanacademy.org",
                ],
            },
            max_results=max_results,
        )

    async def search_news(
        self,
        query: str,
        max_results: int | None = None,
    ) -> list[dict]:
        return await self._search(
            query,
            config={
                "search_depth": "advanced",
                "max_results": 15,
                "include_answer": True,
                "topic": "general",
            },
            max_results=max_results,
        )

    async def search_opportunities(
        self,
        query: str,
        max_results: int | None = None,
    ) -> list[dict]:
        """Override: Use DirectSourceScraper instead of Tavily for opportunities."""
        logger.info("SearchClient: Using DirectSourceScraper for opportunities (Tavily bypass)")
        scraper = _get_direct_scraper()
        return await scraper.scrape_opportunities()

    async def search_corpus(
        self,
        query: str,
        max_results: int | None = None,
    ) -> list[dict]:
        return await self._search(
            query,
            config={
                "search_depth": "advanced",
                "max_results": 10,
                "include_domains": [
                    "huggingface.co",
                    "github.com",
                    "oscar-corpus.com",
                    "ldc.upenn.edu",
                    "elra.info",
                    "clarin.eu",
                    "dumps.wikimedia.org",
                    "paperswithcode.com",
                    "kaggle.com",
                    "zenodo.org",
                    "figshare.com",
                    "commoncrawl.org",
                ],
            },
            max_results=max_results,
        )

    async def search_web(self, query: str, max_results: int = 15) -> list[dict]:
        """Compatibility API used by legacy callers."""
        throttle_seconds = getattr(settings, "SCRAPING_API_CALL_DELAY_SECONDS", 0)
        try:
            delay_seconds = max(0.0, float(throttle_seconds))
        except (TypeError, ValueError):
            delay_seconds = 0.0
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
        return await self._search(
            query,
            config={
                "search_depth": "advanced",
                "max_results": max_results,
                "include_answer": True,
                "include_raw_content": True,
                "topic": "general",
            },
            max_results=max_results,
        )


__all__ = ["TavilySearchClient"]
