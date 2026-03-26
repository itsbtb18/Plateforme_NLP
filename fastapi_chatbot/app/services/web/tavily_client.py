"""
Tavily search client — user-triggered web search mode.

This is a DIRECT web-answer path, separate from the RAG pipeline.
Results are NOT merged into RRF ranking — they are returned as-is
with citations/URLs for the frontend to display.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def search_tavily(
    query: str,
    *,
    search_depth: str = "advanced",
    max_results: int = 5,
    include_answer: bool = True,
    include_raw_content: bool = False,
) -> Dict[str, Any]:
    """Perform a Tavily web search and return structured results.

    Args:
        query: user query text
        search_depth: "basic" (fast) or "advanced" (thorough, longer answers)
        max_results: max web results to return
        include_answer: whether to include Tavily's AI-generated answer
        include_raw_content: whether to include full page content

    Returns:
        Dict with keys:
          - answer: str (Tavily's generated answer, if available)
          - results: list of {title, url, content, score}
          - source_urls: list of URLs found
          - response_time: float (seconds)
          - query: str (original query)
    """
    if not settings.TAVILY_ENABLED or not settings.TAVILY_API_KEY:
        logger.warning("Tavily search skipped: disabled or no API key")
        return {
            "answer": "Web search is not configured. Please set the TAVILY_API_KEY.",
            "results": [],
            "source_urls": [],
            "response_time": 0,
            "query": query,
        }

    # Import lazily to avoid import errors when tavily-python isn't installed
    try:
        from tavily import TavilyClient
    except ImportError:
        logger.warning("tavily-python package not installed — Tavily search unavailable")
        return {
            "answer": "Web search package not available. Please install tavily-python.",
            "results": [],
            "source_urls": [],
            "response_time": 0,
            "query": query,
        }

    try:
        start = time.monotonic()
        client = TavilyClient(api_key=settings.TAVILY_API_KEY)

        response = client.search(
            query=query,
            search_depth=search_depth,
            max_results=max_results,
            include_answer=include_answer,
            include_raw_content=include_raw_content,
        )

        elapsed = time.monotonic() - start

        results = []
        source_urls = []
        for r in response.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "score": r.get("score", 0),
            })
            if r.get("url"):
                source_urls.append(r["url"])

        answer = response.get("answer", "") or ""

        logger.info(
            "Tavily search complete: query='%s' depth=%s results=%d latency=%.2fs",
            query[:60], search_depth, len(results), elapsed,
        )

        return {
            "answer": answer,
            "results": results,
            "source_urls": source_urls,
            "response_time": round(elapsed, 2),
            "query": query,
        }

    except Exception as e:
        logger.error("Tavily search failed: %s", e)
        return {
            "answer": f"Web search encountered an error: {str(e)}",
            "results": [],
            "source_urls": [],
            "response_time": 0,
            "query": query,
        }
