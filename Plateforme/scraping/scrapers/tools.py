"""Tavily + Groq based tools scraper."""

from __future__ import annotations

import logging
import time

from asgiref.sync import async_to_sync
from django.db import transaction
from django.utils import timezone

from scraping.extractors.tools.llm_tool_extractor import LLMToolExtractor
from scraping.field_mapping import get_auto_translate_fields
from scraping.network.search_client import TavilySearchClient
from scraping.translation.arabic_translator import ArabicTranslator
from scraping.utils import infer_translation_status

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

        if not search_client.is_enabled:
            self._log_error(
                "tools_search_unavailable",
                search_client.disabled_reason or "Tavily search client unavailable",
                source=self.name,
            )
            return

        search_queries = self.get_active_search_queries(self.category)
        if not search_queries:
            logger.warning(
                "No active search queries configured for category '%s'.", self.category
            )
            return

        combined_results: list[dict] = []
        total_queries = len(search_queries)
        self.emit_progress(
            "discovery",
            0,
            total_queries,
            "🔍 Starting discovery...",
            current_source=self.name,
        )
        for query_index, query in enumerate(search_queries, start=1):
            self.emit_progress(
                "discovery",
                query_index,
                total_queries,
                f"🔍 Searching: {query}",
                current_source=query,
                current_item=query,
            )
            try:
                time.sleep(self.API_CALL_DELAY_SECONDS)
                results = async_to_sync(search_client.search_tools)(query)
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
            total_batches = 1
            self.emit_progress(
                "extraction",
                0,
                total_batches,
                "🤖 Starting extraction...",
                current_item="Batch 0/1",
            )
            self.emit_progress(
                "extraction",
                1,
                total_batches,
                "🤖 Extracting batch 1/1",
                current_item="Batch 1/1",
            )
            candidates = async_to_sync(extractor.extract_tools_from_search)(
                combined_results
            )
        except Exception as exc:
            self._log_error("tools_llm_extraction_failed", str(exc), source=self.name)
            return

        if not candidates:
            logger.warning("No tool candidates extracted from Tavily results.")
            return

        translator = ArabicTranslator()
        fields_to_translate = [
            "title_ar",
            "description_ar",
            "short_description_ar",
            *get_auto_translate_fields(self.category),
        ]
        candidates = translator.batch_translate(candidates, fields=fields_to_translate)

        author = self.get_system_user()

        total_candidates = len(candidates)
        self.emit_progress(
            "validation",
            0,
            total_candidates,
            "✅ Starting validation...",
        )
        for candidate_index, candidate in enumerate(candidates, start=1):
            self.emit_progress(
                "saving",
                candidate_index,
                total_candidates,
                f"💾 Saving item {candidate_index}/{total_candidates}",
                current_item=(
                    str(
                        candidate.get("title_en") or candidate.get("title") or ""
                    ).strip()
                    if isinstance(candidate, dict)
                    else ""
                ),
            )
            if not isinstance(candidate, dict):
                self.items_skipped += 1
                continue

            normalized = self._normalize_candidate(candidate)
            if normalized is None:
                self.items_skipped += 1
                continue

            if not self.passes_min_confidence_to_save(normalized):
                self.items_skipped += 1
                continue

            lookup = (
                {"github_url": normalized["github_url"]}
                if normalized["github_url"]
                else {"title_en": normalized["title_en"]}
            )

            defaults = {
                "title": normalized["title_en"],
                "title_ar": normalized["title_ar"] or "",
                "description": normalized["description_en"],
                "description_en": normalized["description_en"],
                "description_ar": normalized["description_ar"] or "",
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
                "approval_status": str(
                    normalized.get("approval_status") or "pending"
                ).lower(),
                "is_approved": False,
                "update_date": timezone.now(),
            }

            try:
                now = timezone.now()
                with transaction.atomic():
                    tool = NLPTool.objects.select_for_update().filter(**lookup).first()
                    if tool is not None:
                        defaults["last_scraped_at"] = now
                        defaults["update_counter"] = (
                            int(getattr(tool, "update_counter", 0) or 0) + 1
                        )
                        if self._is_approved_record(tool):
                            defaults = self._build_terminal_status_update_defaults(
                                existing_obj=tool,
                                incoming_defaults=defaults,
                                metadata_fields={"last_scraped_at", "update_counter"},
                            )
                        for field_name, field_value in defaults.items():
                            setattr(tool, field_name, field_value)
                        tool.save()
                        created = False
                    else:
                        semantic_queryset = self._recent_dedup_queryset(
                            NLPTool.objects.only("id", "title", "title_en")
                        )
                        semantic_tool, semantic_score = self._find_semantic_title_match(
                            semantic_queryset,
                            normalized["title_en"],
                            title_fields=("title_en", "title"),
                        )
                        if semantic_tool is not None:
                            tool = semantic_tool
                            defaults["last_scraped_at"] = now
                            defaults["update_counter"] = (
                                int(getattr(tool, "update_counter", 0) or 0) + 1
                            )
                            if self._is_approved_record(tool):
                                defaults = self._build_terminal_status_update_defaults(
                                    existing_obj=tool,
                                    incoming_defaults=defaults,
                                    metadata_fields={"last_scraped_at", "update_counter"},
                                )
                            for field_name, field_value in defaults.items():
                                setattr(tool, field_name, field_value)
                            tool.save()
                            created = False
                        else:
                            defaults["last_scraped_at"] = now
                            defaults.setdefault("update_counter", 0)
                            create_data = dict(defaults)
                            create_data.update(lookup)
                            tool = NLPTool.objects.create(**create_data)
                            created = True
            except Exception as exc:
                self._log_error(
                    "tool_upsert_failed",
                    str(exc),
                    source=normalized["title_en"],
                    url=normalized["access_link"],
                )
                self.items_skipped += 1
                continue

            if created:
                self.items_created += 1
            else:
                self.items_updated += 1
            self._track_saved_item_status(normalized)

            self.results.append(
                {
                    "title": normalized["title_en"],
                    "description": self.truncate(normalized["description_en"], 400),
                    "type": normalized["tool_type"],
                    "url": normalized["access_link"],
                    "source_name": "Tavily Search + Groq",
                    "source_url": normalized["access_link"],
                    "title_en": normalized["title_en"],
                    "title_ar": normalized["title_ar"],
                    "description_en": normalized["description_en"],
                    "description_ar": normalized["description_ar"],
                    "access_link": normalized["access_link"],
                    "keywords": normalized["capabilities"],
                    "supported_languages": ["ar"],
                    "translation_status": normalized.get(
                        "translation_status", "pending"
                    ),
                    "relevance_score": normalized.get("relevance_score"),
                    "extraction_confidence": normalized.get("extraction_confidence"),
                }
            )

    def _normalize_candidate(self, item: dict):
        title_en = self._safe_text(item.get("title_en"))
        description_en = self._safe_text(item.get("description_en"))
        if not title_en:
            return None
        if not description_en:
            description_en = "[NEEDS RESEARCH]"

        title_ar = self._safe_text(item.get("title_ar")) or None
        description_ar = self._safe_text(item.get("description_ar")) or None
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

        access_link = (
            github_url
            or paper_url
            or self._safe_text(item.get("url"))
            or self._safe_text(item.get("source_url"))
            or self._safe_text(item.get("access_link"))
            or "[NEEDS RESEARCH]"
        )

        translation_status = infer_translation_status(
            raw_status=self._safe_text(item.get("translation_status")) or "pending",
            english_values=[title_en, description_en],
            arabic_values=[title_ar, description_ar],
        )

        return {
            "title_en": title_en[:200],
            "title_ar": title_ar[:200] if title_ar else None,
            "description_en": description_en,
            "description_ar": description_ar if description_ar else None,
            "github_url": github_url,
            "paper_url": paper_url,
            "license": license_value,
            "capabilities": capabilities,
            "access_link": access_link,
            "tool_type": self._map_tool_type(capabilities, description_en),
            "translation_status": translation_status,
            "relevance_score": item.get("relevance_score"),
            "extraction_confidence": item.get("extraction_confidence"),
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
