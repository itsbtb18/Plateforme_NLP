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
        self.client = None
        self._client_kwargs = client_kwargs
        self._disabled_reason = ""
        self._disabled_logged = False

        self.api_keys = []
        if api_key:
            self.api_keys.append(api_key)
        else:
            self.api_keys = self._resolve_api_keys()

        self.current_key_idx = 0
        if not self.api_keys:
            self._disabled_reason = "No Tavily API keys configured"
            return

        try:
            from tavily import TavilyClient
        except ImportError as exc:
            raise RuntimeError(
                "tavily-python is not installed. Install it with: pip install tavily-python"
            ) from exc

        self.client = TavilyClient(
            api_key=self.api_keys[self.current_key_idx], **self._client_kwargs
        )

    @property
    def is_enabled(self) -> bool:
        return self.client is not None

    @property
    def disabled_reason(self) -> str:
        return self._disabled_reason

    @staticmethod
    def _resolve_api_keys() -> list[str]:
        keys = []
        env_vars = [
            "SCRAPING_TAVILY_API_KEY",
            "SCRAPING_TAVILY_BACKUP_API_KEY",
            "TAVILY_API_KEY",
        ]
        for env_var in env_vars:
            val = getattr(settings, env_var, "") or os.environ.get(env_var, "")
            if val and val.strip() and val.strip() not in keys:
                keys.append(val.strip())
        return keys

    async def _search(
        self,
        query: str,
        config: dict[str, Any],
        *,
        max_results: int | None = None,
    ) -> list[dict]:
        """Search Tavily with per-category configuration and return normalized items."""
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
            ):
                self.current_key_idx += 1
                if self.current_key_idx < len(self.api_keys):
                    logger.warning(
                        "Tavily API key exhausted. Switching to backup key..."
                    )
                    from tavily import TavilyClient

                    self.client = TavilyClient(
                        api_key=self.api_keys[self.current_key_idx],
                        **self._client_kwargs,
                    )
                    try:
                        response = await asyncio.to_thread(
                            self.client.search,
                            query=query_text,
                            **request_config,
                        )
                    except Exception as retry_exc:
                        logger.error(
                            "Tavily search failed with backup key: %s", retry_exc
                        )
                        return []
                else:
                    self._disabled_reason = "Tavily plan usage limits reached on all keys; client disabled for this run"
                    self.client = None
                    logger.warning(
                        "Tavily disabled for current run due to plan usage limit: %s",
                        message,
                    )
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
        return await self._search(
            query,
            config={
                "search_depth": "advanced",
                "max_results": 10,
                "include_answer": True,
                "include_raw_content": True,
                "include_domains": [
                    "aclanthology.org",
                    "aclweb.org",
                    "arxiv.org",
                    "semanticscholar.org",
                    "eventbrite.com",
                    "confcal.net",
                    "wikicfp.com",
                    "researchgate.net",
                ],
                "topic": "general",
            },
            max_results=max_results,
        )

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
                "max_results": 8,
                "include_domains": [
                    "coursera.org",
                    "edx.org",
                    "udemy.com",
                    "youtube.com",
                    "mooc.org",
                    "futurelearn.com",
                    "datacamp.com",
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
                "search_depth": "basic",
                "max_results": 15,
                "include_answer": True,
                "topic": "news",
                "days": 30,
            },
            max_results=max_results,
        )

    async def search_opportunities(
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
                    "academicpositions.eu",
                    "scholarshipdb.net",
                    "euraxess.ec.europa.eu",
                    "jobs.ac.uk",
                    "mbzuai.ac.ae",
                    "qcri.org",
                    "kaust.edu.sa",
                    "aub.edu.lb",
                ],
            },
            max_results=max_results,
        )

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
                    "paperswithcode.com/datasets",
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
