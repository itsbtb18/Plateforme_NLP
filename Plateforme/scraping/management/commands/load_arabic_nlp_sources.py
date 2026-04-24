import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from scraping.constants import CANONICAL_CATEGORIES
from scraping.models import ScrapingSource, SearchQuery


class Command(BaseCommand):
    help = (
        "Load curated Arabic NLP scraping sources and Tavily query templates "
        "from scraping/fixtures/arabic_nlp_sources.json."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fixture",
            type=str,
            default=str(
                Path(settings.BASE_DIR)
                / "scraping"
                / "fixtures"
                / "arabic_nlp_sources.json"
            ),
            help="Path to arabic_nlp_sources fixture JSON.",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help=(
                "Delete existing ScrapingSource and SearchQuery rows for "
                "canonical categories before loading."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate fixture and print summary without writing to database.",
        )

    def handle(self, *args, **options):
        fixture_path = Path(options["fixture"]).expanduser().resolve()
        replace = bool(options["replace"])
        dry_run = bool(options["dry_run"])

        if not fixture_path.exists():
            raise CommandError(f"Fixture not found: {fixture_path}")

        payload = self._load_fixture(fixture_path)
        sources, query_templates = self._parse_payload(payload)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run successful: "
                    f"sources={len(sources)}, "
                    f"template_categories={len(query_templates)}"
                )
            )
            return

        with transaction.atomic():
            deleted_sources = 0
            deleted_queries = 0
            if replace:
                deleted_sources, _ = ScrapingSource.objects.filter(
                    category__in=CANONICAL_CATEGORIES
                ).delete()
                deleted_queries, _ = SearchQuery.objects.filter(
                    category__in=CANONICAL_CATEGORIES
                ).delete()

            created_sources = 0
            updated_sources = 0
            created_queries = 0
            reactivated_queries = 0

            for source_data in sources:
                normalized = self._normalize_source(source_data)
                source, created = self._upsert_source(normalized)
                if created:
                    created_sources += 1
                else:
                    updated_sources += 1

                c_created, c_reactivated = self._upsert_search_queries(
                    category=source.category,
                    query_texts=normalized["search_queries"],
                )
                created_queries += c_created
                reactivated_queries += c_reactivated

            for category, query_texts in query_templates.items():
                c_created, c_reactivated = self._upsert_search_queries(
                    category=category,
                    query_texts=query_texts,
                )
                created_queries += c_created
                reactivated_queries += c_reactivated

        summary_parts = [
            f"sources_created={created_sources}",
            f"sources_updated={updated_sources}",
            f"queries_created={created_queries}",
            f"queries_reactivated={reactivated_queries}",
        ]
        if replace:
            summary_parts.insert(0, f"deleted_sources={deleted_sources}")
            summary_parts.insert(1, f"deleted_queries={deleted_queries}")

        self.stdout.write(
            self.style.SUCCESS("Arabic NLP sources loaded: " + ", ".join(summary_parts))
        )

    @staticmethod
    def _load_fixture(path: Path) -> dict[str, Any] | list[dict[str, Any]]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in fixture {path}: {exc}") from exc

    def _parse_payload(
        self,
        payload: dict[str, Any] | list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
        if isinstance(payload, list):
            sources = payload
            query_templates: dict[str, list[str]] = {}
        elif isinstance(payload, dict):
            sources = payload.get("sources", [])
            query_templates = payload.get("query_templates", {})
        else:
            raise CommandError("Fixture root must be an object or array.")

        if not isinstance(sources, list):
            raise CommandError("Fixture 'sources' must be a list.")

        normalized_templates: dict[str, list[str]] = {}
        if query_templates:
            if not isinstance(query_templates, dict):
                raise CommandError("Fixture 'query_templates' must be an object.")

            for raw_category, raw_queries in query_templates.items():
                category = str(raw_category or "").strip().lower()
                if category not in CANONICAL_CATEGORIES:
                    continue
                normalized_templates[category] = self._normalize_queries(raw_queries)

        return sources, normalized_templates

    def _normalize_source(self, row: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(row, dict):
            raise CommandError("Each source entry must be a JSON object.")

        name = str(row.get("name", "")).strip()
        url = str(row.get("url", "")).strip()
        category = str(row.get("category", "")).strip().lower()
        description = str(row.get("description", "")).strip()

        if not name:
            raise CommandError("Source entry missing required field: name")
        if not url:
            raise CommandError(f"Source '{name}' missing required field: url")
        if category not in CANONICAL_CATEGORIES:
            raise CommandError(
                f"Source '{name}' has unsupported category '{category}'. "
                f"Allowed: {', '.join(CANONICAL_CATEGORIES)}"
            )

        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CommandError(f"Source '{name}' has invalid URL: {url}")

        priority = self._clamp_int(row.get("priority", 3), min_value=1, max_value=5)
        trust_score = self._clamp_float(
            row.get("trust_score", 0.9),
            min_value=0.0,
            max_value=1.0,
        )
        language_focus = str(row.get("language_focus", "arabic")).strip().lower()
        queries = self._normalize_queries(row.get("search_queries", []))

        return {
            "name": name,
            "url": url,
            "category": category,
            "description": description,
            "is_active": bool(row.get("is_active", True)),
            "priority": priority,
            "search_queries": queries,
            "language_focus": language_focus or "arabic",
            "trust_score": trust_score,
        }

    def _upsert_source(
        self, source_data: dict[str, Any]
    ) -> tuple[ScrapingSource, bool]:
        category = source_data["category"]
        url = source_data["url"]

        source, created = ScrapingSource.objects.get_or_create(
            category=category,
            url=url,
            defaults={
                "name": source_data["name"],
                "base_url": url,
                "description": source_data["description"],
                "is_active": source_data["is_active"],
                "is_default": True,
                "source_type": self._infer_source_type(url),
                "scrape_config": self._merge_scrape_config({}, source_data),
            },
        )

        if created:
            return source, True

        source.name = source_data["name"]
        source.base_url = url
        source.description = source_data["description"]
        source.is_active = source_data["is_active"]
        source.is_default = True
        source.source_type = self._infer_source_type(url)
        source.scrape_config = self._merge_scrape_config(
            source.scrape_config or {},
            source_data,
        )
        source.save(
            update_fields=[
                "name",
                "base_url",
                "description",
                "is_active",
                "is_default",
                "source_type",
                "scrape_config",
            ]
        )
        return source, False

    def _upsert_search_queries(
        self,
        *,
        category: str,
        query_texts: list[str],
    ) -> tuple[int, int]:
        created = 0
        reactivated = 0

        for query_text in self._normalize_queries(query_texts):
            query, was_created = SearchQuery.objects.get_or_create(
                category=category,
                query_text=query_text,
                defaults={"is_active": True},
            )
            if was_created:
                created += 1
                continue

            if not query.is_active:
                query.is_active = True
                query.save(update_fields=["is_active"])
                reactivated += 1

        return created, reactivated

    @staticmethod
    def _merge_scrape_config(
        existing: dict[str, Any],
        source_data: dict[str, Any],
    ) -> dict[str, Any]:
        config = dict(existing)
        config.update(
            {
                "priority": source_data["priority"],
                "trust_score": source_data["trust_score"],
                "language_focus": source_data["language_focus"],
                "search_queries": source_data["search_queries"],
                "seed_profile": "arabic_nlp_sources",
            }
        )
        return config

    @staticmethod
    def _normalize_queries(raw_queries: Any) -> list[str]:
        if not isinstance(raw_queries, list):
            return []

        seen: set[str] = set()
        normalized: list[str] = []

        for raw in raw_queries:
            query = str(raw or "").strip()
            if not query:
                continue
            lowered = query.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(query)

        return normalized

    @staticmethod
    def _infer_source_type(url: str) -> str:
        lowered = (url or "").lower()
        if "/api" in lowered or "api." in lowered:
            return "api"
        return "web"

    @staticmethod
    def _clamp_int(value: Any, *, min_value: int, max_value: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = min_value
        return max(min_value, min(max_value, parsed))

    @staticmethod
    def _clamp_float(value: Any, *, min_value: float, max_value: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = min_value
        parsed = max(min_value, min(max_value, parsed))
        return round(parsed, 4)
