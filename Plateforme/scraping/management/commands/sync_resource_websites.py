from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from scraping.constants import CANONICAL_CATEGORIES
from scraping.models import ScrapingSource, SearchQuery


URL_PATTERN = re.compile(r"https?://[^\s\]\)>\",']+", re.IGNORECASE)
DOMAIN_PATTERN = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}(?:/[^\s\]\)>\",']*)?",
    re.IGNORECASE,
)


SECTION_TO_CATEGORY: dict[str, str] = {
    "corpus websites": "corpus",
    "courses websites": "courses",
    "opportunities websites": "opportunities",
    "news websites": "news",
    "events websites": "events",
    "tools websites": "tools",
    "apis websites": "tools",
}


QUERY_HINTS: dict[str, list[str]] = {
    "events": [
        "Arabic NLP conference",
        "Arabic AI workshop",
        "MENA NLP events",
    ],
    "news": [
        "Arabic NLP news",
        "AI news arabic",
        "Arabic language technology updates",
    ],
    "opportunities": [
        "Arabic NLP jobs",
        "NLP opportunities MENA",
        "Arabic AI internships",
    ],
    "tools": [
        "Arabic NLP tools",
        "Arabic NLP models",
        "Arabic NLP github",
    ],
    "corpus": [
        "Arabic NLP corpus",
        "Arabic datasets NLP",
        "Arabic language corpus",
    ],
    "courses": [
        "Arabic NLP course",
        "NLP course arabic",
        "AI course arabic language",
    ],
}

SITE_QUERY_TERMS: dict[str, str] = {
    "events": "AI NLP conference workshop event Arab MENA North Africa Algeria",
    "news": "AI NLP news updates arabic arab world",
    "opportunities": "AI NLP jobs internships fellowship Arab MENA",
    "tools": "Arabic NLP tools models datasets API",
    "corpus": "Arabic NLP corpus dataset text resources",
    "courses": "Arabic NLP AI courses training learning",
}


def _canonical_host(host: str) -> str:
    lowered = (host or "").strip().lower()
    if lowered.startswith("www."):
        return lowered[4:]
    return lowered


def _infer_source_type(url: str) -> str:
    lowered = url.lower()
    if "/api" in lowered or "api." in lowered:
        return "api"
    return "web"


def _is_probably_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _normalize_dashes(text: str) -> str:
    return (
        (text or "")
        .replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )


def _normalize_url(raw: str) -> str:
    cleaned = _normalize_dashes((raw or "").strip())
    cleaned = cleaned.rstrip(".,;)]}")
    if not cleaned:
        return ""
    if not cleaned.lower().startswith(("http://", "https://")):
        cleaned = f"https://{cleaned}"
    parsed = urlparse(cleaned)
    if not _is_probably_valid_url(cleaned):
        return ""
    path = parsed.path or ""
    return f"{parsed.scheme.lower()}://{_canonical_host(parsed.netloc)}{path}"


def _extract_urls_from_line(line: str) -> list[str]:
    candidates: set[str] = set()
    text = _normalize_dashes(line or "")
    for match in URL_PATTERN.findall(text):
        normalized = _normalize_url(match)
        if normalized:
            candidates.add(normalized)
    for match in DOMAIN_PATTERN.findall(text):
        normalized = _normalize_url(match)
        if normalized:
            candidates.add(normalized)
    return sorted(candidates)


def _extract_section_key(line: str) -> str | None:
    text = (line or "").strip().lower().rstrip(":")
    if text.startswith("#"):
        text = text.lstrip("#").strip()
    for key in SECTION_TO_CATEGORY:
        if key in text:
            return key
    return None


def _source_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = _canonical_host(parsed.netloc)
    path = (parsed.path or "").strip("/")
    if path:
        segment = path.split("/")[0]
        return f"{host} - {segment}"[:180]
    return host[:180]


def _build_site_specific_query(category: str, url: str) -> str:
    parsed = urlparse(url)
    host = _canonical_host(parsed.netloc)
    path = (parsed.path or "").strip("/")
    scope = f"site:{host}"
    if path:
        scope = f"{scope}/{path}"
    terms = SITE_QUERY_TERMS.get(category, "NLP AI")
    query = f"{scope} {terms}".strip()
    return query[:500]


class Command(BaseCommand):
    help = (
        "Sync websites/APIs from website_to_add_to_scraping.md into ScrapingSource "
        "and SearchQuery for future scraper runs."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default="website_to_add_to_scraping.md",
            help="Path to markdown file with resources.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and print summary without DB writes.",
        )

    def handle(self, *args, **options):
        file_path = self._resolve_markdown_path(str(options.get("file") or ""))
        dry_run = bool(options.get("dry_run"))

        if not file_path.exists():
            raise CommandError(f"Markdown file not found: {file_path}")

        parsed_sources = self._parse_markdown(file_path)
        if not parsed_sources:
            raise CommandError("No websites found in markdown file.")

        if dry_run:
            by_category: dict[str, int] = {}
            for source in parsed_sources:
                by_category[source["category"]] = by_category.get(source["category"], 0) + 1
            self.stdout.write(
                self.style.WARNING(
                    "Dry run successful: "
                    + ", ".join(f"{k}={v}" for k, v in sorted(by_category.items()))
                )
            )
            return

        created_sources = 0
        updated_sources = 0
        created_queries = 0
        reactivated_queries = 0

        with transaction.atomic():
            for source_data in parsed_sources:
                source, created = ScrapingSource.objects.get_or_create(
                    category=source_data["category"],
                    url=source_data["url"],
                    defaults={
                        "name": source_data["name"],
                        "base_url": source_data["url"],
                        "description": source_data["description"],
                        "source_type": source_data["source_type"],
                        "is_active": True,
                        "is_default": True,
                        "scrape_config": {
                            "seed_profile": "website_to_add_to_scraping",
                            "priority": 2,
                            "trust_score": 0.9,
                            "search_queries": source_data["search_queries"],
                        },
                    },
                )

                if created:
                    created_sources += 1
                else:
                    source.name = source_data["name"]
                    source.base_url = source_data["url"]
                    source.description = source_data["description"]
                    source.source_type = source_data["source_type"]
                    source.is_active = True
                    source.is_default = True
                    config = dict(source.scrape_config or {})
                    config.setdefault("seed_profile", "website_to_add_to_scraping")
                    config.setdefault("priority", 2)
                    config.setdefault("trust_score", 0.9)
                    config["search_queries"] = source_data["search_queries"]
                    source.scrape_config = config
                    source.save(
                        update_fields=[
                            "name",
                            "base_url",
                            "description",
                            "source_type",
                            "is_active",
                            "is_default",
                            "scrape_config",
                        ]
                    )
                    updated_sources += 1

                for query_text in source_data["search_queries"]:
                    query, query_created = SearchQuery.objects.get_or_create(
                        category=source_data["category"],
                        query_text=query_text,
                        defaults={"is_active": True},
                    )
                    if query_created:
                        created_queries += 1
                    elif not query.is_active:
                        query.is_active = True
                        query.save(update_fields=["is_active"])
                        reactivated_queries += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Resource websites sync complete: "
                f"sources_created={created_sources}, "
                f"sources_updated={updated_sources}, "
                f"queries_created={created_queries}, "
                f"queries_reactivated={reactivated_queries}"
            )
        )

    def _parse_markdown(self, file_path: Path) -> list[dict[str, str | list[str]]]:
        raw = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = raw.splitlines()
        current_section: str | None = None
        by_key: dict[tuple[str, str], dict[str, str | list[str]]] = {}

        for line in lines:
            section = _extract_section_key(line)
            if section is not None:
                current_section = section
                continue

            if current_section is None:
                continue

            category = SECTION_TO_CATEGORY.get(current_section)
            if category not in CANONICAL_CATEGORIES:
                continue

            for url in _extract_urls_from_line(line):
                parsed = urlparse(url)
                host = _canonical_host(parsed.netloc)
                key = (category, url)

                if key in by_key:
                    continue

                source_name = _source_name_from_url(url)
                description = (
                    f"Imported from website_to_add_to_scraping.md ({current_section})"
                )
                queries = [
                    _build_site_specific_query(category, url),
                    *list(QUERY_HINTS.get(category, [])),
                ]
                if host.endswith("huggingface.co") and category == "tools":
                    queries.extend(
                        [
                            "Hugging Face Arabic NLP model",
                            "Hugging Face Arabic NLP dataset",
                        ]
                    )
                source = {
                    "name": source_name,
                    "url": url,
                    "category": category,
                    "description": description,
                    "source_type": _infer_source_type(url),
                    "search_queries": self._dedupe_queries(queries),
                }
                by_key[key] = source

        return sorted(by_key.values(), key=lambda row: (str(row["category"]), str(row["name"])))

    @staticmethod
    def _dedupe_queries(queries: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for query in queries:
            cleaned = str(query or "").strip()
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(cleaned)
        return normalized

    @staticmethod
    def _resolve_markdown_path(raw_path: str) -> Path:
        raw = (raw_path or "").strip()
        if not raw:
            return Path("").resolve()

        candidate = Path(raw).expanduser()
        if candidate.is_absolute() and candidate.exists():
            return candidate.resolve()

        search_roots = [
            Path.cwd(),
            Path(settings.BASE_DIR),
            Path(settings.BASE_DIR).parent,
        ]
        for root in search_roots:
            resolved = (root / candidate).resolve()
            if resolved.exists():
                return resolved

        return candidate.resolve()