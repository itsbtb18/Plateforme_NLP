"""Tavily + Groq based tools scraper."""

from __future__ import annotations

import logging
import time

from asgiref.sync import async_to_sync
from django.utils import timezone

from scraping.extractors.tools.llm_tool_extractor import LLMToolExtractor
from scraping.network.search_client import TavilySearchClient

from .base import BaseScraper

logger = logging.getLogger(__name__)


class ToolScraper(BaseScraper):
    """Discover Arabic NLP tools from web search and LLM extraction."""

    name = "Arabic NLP Tools (Tavily + Groq)"
    category = "tools"
    API_CALL_DELAY_SECONDS = 2

    def scrape(self):
        from resources.models import NLPTool

        try:
            search_client = TavilySearchClient()
            extractor = LLMToolExtractor()
        except Exception as exc:
            self._log_error("tools_init_failed", str(exc), source=self.name)
            logger.warning("Tool scraper initialization failed: %s", exc)
            return

        search_queries = self.get_active_search_queries(self.category)
        if not search_queries:
            logger.warning(
                "No active search queries configured for category '%s'.", self.category
            )
            return

        combined_results: list[dict] = []
        for query in search_queries:
            try:
                time.sleep(self.API_CALL_DELAY_SECONDS)
                results = async_to_sync(search_client.search_web)(query, max_results=12)
            except Exception as exc:
                self._log_error(
                    "tools_tavily_search_failed",
                    str(exc),
                    source=self.name,
                    url=query,
                )
                continue

            if results:
                combined_results.extend(results)

        if not combined_results:
            logger.warning("No tool search results returned by Tavily.")
            return

        try:
            time.sleep(self.API_CALL_DELAY_SECONDS)
            candidates = async_to_sync(extractor.extract_tools_from_search)(
                combined_results
            )
        except Exception as exc:
            self._log_error("tools_llm_extraction_failed", str(exc), source=self.name)
            return

        if not candidates:
            logger.warning("No tool candidates extracted from Tavily results.")
            return

        author = self.get_system_user()

        for candidate in candidates:
            if not isinstance(candidate, dict):
                self.items_skipped += 1
                continue

            normalized = self._normalize_candidate(candidate)
            if normalized is None:
                self.items_skipped += 1
                continue

            lookup = (
                {"github_url": normalized["github_url"]}
                if normalized["github_url"]
                else {"title_en": normalized["title_en"]}
            )

            defaults = {
                "title": normalized["title_en"],
                "title_ar": normalized["title_ar"],
                "description": normalized["description_en"],
                "description_en": normalized["description_en"],
                "description_ar": normalized["description_ar"],
                "tool_type": normalized["tool_type"],
                "version": "latest",
                "access_link": normalized["access_link"],
                "documentation_link": normalized["paper_url"]
                or normalized["github_url"],
                "github_url": normalized["github_url"],
                "paper_url": normalized["paper_url"],
                "license": normalized["license"],
                "source_url": normalized["access_link"],
                "source_name": "Tavily Search + Groq",
                "supported_languages": "ar",
                "language": "ar",
                "keywords": ", ".join(normalized["capabilities"])
                if normalized["capabilities"]
                else None,
                "entities": {"capabilities": normalized["capabilities"]},
                "author": author,
                "approval_status": "pending",
                "is_approved": False,
                "update_date": timezone.now(),
            }

            try:
                tool, created = NLPTool.objects.update_or_create(
                    **lookup,
                    defaults=defaults,
                )
            except Exception as exc:
                self._log_error(
                    "tool_upsert_failed",
                    str(exc),
                    source=normalized["title_en"],
                    url=normalized["access_link"],
                )
                self.items_skipped += 1
                continue

            forced_updates = {}
            if tool.approval_status != "pending":
                forced_updates["approval_status"] = "pending"
            if bool(tool.is_approved):
                forced_updates["is_approved"] = False
            if forced_updates:
                NLPTool.objects.filter(pk=tool.pk).update(**forced_updates)

            if created:
                self.items_created += 1
            else:
                self.items_updated += 1

            self.results.append(
                {
                    "title": normalized["title_en"],
                    "description": self.truncate(normalized["description_en"], 400),
                    "type": normalized["tool_type"],
                    "url": normalized["access_link"],
                    "source_name": "Tavily Search + Groq",
                    "source_url": normalized["access_link"],
                    "title_en": normalized["title_en"],
                    "description_en": normalized["description_en"],
                }
            )

    def _normalize_candidate(self, item: dict):
        title_en = self._safe_text(item.get("title_en"))
        description_en = self._safe_text(item.get("description_en"))
        if not title_en or not description_en:
            return None

        title_ar = self._safe_text(item.get("title_ar")) or title_en
        description_ar = self._safe_text(item.get("description_ar")) or description_en
        github_url = self._safe_text(item.get("github_url"))
        paper_url = self._safe_text(item.get("paper_url"))
        license_value = self._safe_text(item.get("license"))

        capabilities_raw = item.get("capabilities")
        capabilities = []
        if isinstance(capabilities_raw, list):
            capabilities = [
                str(value).strip()[:120]
                for value in capabilities_raw
                if str(value).strip()
            ]

        access_link = github_url or paper_url
        if not access_link:
            return None

        return {
            "title_en": title_en[:200],
            "title_ar": title_ar[:200],
            "description_en": description_en,
            "description_ar": description_ar,
            "github_url": github_url,
            "paper_url": paper_url,
            "license": license_value,
            "capabilities": capabilities,
            "access_link": access_link,
            "tool_type": self._map_tool_type(capabilities, description_en),
        }

    @staticmethod
    def _safe_text(value):
        if value is None:
            return ""
        text = str(value).strip()
        if not text or text.lower() == "null":
            return ""
        return text

    def _map_tool_type(self, capabilities: list[str], description: str) -> str:
        blob = " ".join(capabilities + [description]).lower()
        if "translation" in blob:
            return "machine_translation"
        if "sentiment" in blob:
            return "sentiment_analysis"
        if "named entity" in blob or "ner" in blob:
            return "ner"
        if "part-of-speech" in blob or "pos" in blob:
            return "pos_tagging"
        if "stemming" in blob or "lemmat" in blob:
            return "stemming"
        return "tokenization"
