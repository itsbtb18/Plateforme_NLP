from __future__ import annotations

import logging
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError

from scraping.constants import ALL_CATEGORIES
from scraping.models import ScrapingSource
from scraping.scrapers.selector_discovery import SelectorDiscoveryEngine
from scraping.scraping_settings import scraping_settings as SS

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Auto-discover CSS selectors for a domain and optionally apply them."

    def add_arguments(self, parser):
        parser.add_argument("--domain", required=True, help="Target domain URL")
        parser.add_argument(
            "--category",
            default="news",
            choices=list(ALL_CATEGORIES),
            help="Category used when creating a source on apply",
        )
        parser.add_argument(
            "--sample-count",
            type=int,
            default=SS.DISCOVERY_SAMPLE_COUNT,
            help="Number of sample URLs to analyze",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply top selectors without interactive confirmation",
        )

    def handle(self, *args, **options):
        domain = options["domain"].strip()
        sample_count = int(options["sample_count"])
        force_apply = bool(options["apply"])
        category = options["category"]

        engine = SelectorDiscoveryEngine()

        try:
            sample_urls = engine._discover_sample_urls(domain, count=sample_count)
        except Exception as exc:
            raise CommandError(f"Failed to discover sample URLs: {exc}") from exc

        if not sample_urls:
            raise CommandError("No content-like sample URLs found for this domain")

        self.stdout.write(
            self.style.NOTICE(f"Crawling {domain} ({len(sample_urls)} sample pages)...")
        )

        result = engine.discover(domain, sample_urls=sample_urls)
        recommendations = result["recommendations"]
        recommendations["image"] = self._discover_image_selectors(
            engine,
            sample_urls,
        )

        self._print_ranked_recommendations(recommendations, len(sample_urls))
        self.stdout.write(
            self.style.SUCCESS(f"Overall confidence: {result['confidence']:.0%}")
        )

        should_apply = force_apply
        if not force_apply:
            answer = input("\nApply top selectors to source? [y/N]: ").strip().lower()
            should_apply = answer in {"y", "yes"}

        if not should_apply:
            self.stdout.write("No changes applied.")
            return

        source = self._get_or_create_source(domain, category)
        css_selectors = self._top_selector_map(recommendations)

        # Keep compatibility with existing custom scraper config keys.
        scrape_config = dict(source.scrape_config or {})
        title_selector = css_selectors.get("title_selector")
        desc_selector = css_selectors.get("desc_selector")
        date_selector = css_selectors.get("date_selector")
        author_selector = css_selectors.get("author_selector")
        image_selector = css_selectors.get("image_selector")

        scrape_config.update(
            {
                "title_selector": title_selector,
                "desc_selector": desc_selector,
                "date_selector": date_selector,
                "author_selector": author_selector,
                "image_selector": image_selector,
            }
        )

        missing = [
            field
            for field, value in (
                ("title", title_selector),
                ("summary", desc_selector),
                ("date", date_selector),
                ("author", author_selector),
                ("image", image_selector),
            )
            if value is None
        ]
        if missing:
            missing_text = ", ".join(missing)
            logger.warning("selector_discovery_missing_fields=%s", missing_text)
            self.stdout.write(
                self.style.WARNING(
                    f"No reliable selector found for: {missing_text}. Stored as null."
                )
            )

        source.scrape_config = scrape_config
        source.selector_recommendations = recommendations
        source.selector_confidence = result["confidence"]

        # Optional compatibility for deployments that still have css_selectors.
        if hasattr(source, "css_selectors"):
            source.css_selectors = css_selectors

        source.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Applied selectors to source '{source.name}' ({source.category})"
            )
        )

    def _print_ranked_recommendations(self, recommendations: dict, sample_count: int):
        for field in ("title", "summary", "date", "author", "image"):
            title = field.upper()
            self.stdout.write(f"\n{title} selectors (top 3):")
            rows = recommendations.get(field, [])
            if not rows:
                self.stdout.write("  - no reliable selector found")
                continue

            for idx, row in enumerate(rows[:3], start=1):
                found = int(
                    round(float(row.get("occurrence_ratio", 0.0)) * sample_count)
                )
                self.stdout.write(
                    "  {idx}. {selector:<24} score={score:.2f}  found on {found}/{total} pages  avg_len={avg_len}".format(
                        idx=idx,
                        selector=row.get("selector", ""),
                        score=float(row.get("score", 0.0)),
                        found=found,
                        total=sample_count,
                        avg_len=int(row.get("avg_content_length", 0)),
                    )
                )

    def _top_selector_map(self, recommendations: dict) -> dict[str, str | None]:
        field_map = {
            "title": "title_selector",
            "summary": "desc_selector",
            "date": "date_selector",
            "author": "author_selector",
            "image": "image_selector",
        }
        output: dict[str, str | None] = {}
        for field, key in field_map.items():
            rows = recommendations.get(field, [])
            if rows:
                selector = str(rows[0].get("selector") or "").strip()
                output[key] = selector or None
            else:
                output[key] = None
        return output

    def _discover_image_selectors(
        self,
        engine: SelectorDiscoveryEngine,
        sample_urls: list[str],
    ) -> list[dict]:
        candidates = ["img[src]", "[data-src]", ".thumbnail img", ".cover img"]
        sample_count = max(len(sample_urls), 1)
        stats = {
            selector: {
                "hits": 0,
                "total_length": 0,
                "specificity": 0.0,
                "samples": [],
            }
            for selector in candidates
        }

        for url in sample_urls:
            try:
                response = engine._http_get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")
            except Exception as exc:
                logger.warning(
                    "image_selector_discovery_fetch_failed url=%s err=%s", url, exc
                )
                continue

            for selector in candidates:
                node = soup.select_one(selector)
                if not node:
                    continue
                image_url = (node.get("src") or node.get("data-src") or "").strip()
                if not image_url:
                    continue

                row = stats[selector]
                row["hits"] += 1
                row["total_length"] += len(image_url)
                row["specificity"] += engine._selector_specificity(selector)
                if len(row["samples"]) < 2:
                    row["samples"].append(image_url[:120])

        ranked = []
        for selector, row in stats.items():
            if row["hits"] <= 0:
                continue

            occurrence_ratio = row["hits"] / sample_count
            if occurrence_ratio < engine.min_occurrence_ratio:
                continue

            avg_specificity = row["specificity"] / row["hits"]
            avg_length = row["total_length"] / row["hits"]
            score = (occurrence_ratio * 0.8) + (avg_specificity * 0.2)

            ranked.append(
                {
                    "selector": selector,
                    "score": round(score, 3),
                    "occurrence_ratio": round(occurrence_ratio, 2),
                    "avg_content_length": round(avg_length),
                    "specificity": round(avg_specificity, 2),
                    "sample_texts": row["samples"],
                }
            )

        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[:3]

    def _get_or_create_source(self, domain_url: str, category: str) -> ScrapingSource:
        candidates = ScrapingSource.objects.filter(url=domain_url)
        if candidates.exists():
            return candidates.first()

        candidates = ScrapingSource.objects.filter(base_url=domain_url)
        if candidates.exists():
            return candidates.first()

        parsed = urlparse(domain_url)
        default_name = parsed.netloc or domain_url
        return ScrapingSource.objects.create(
            name=f"Auto {default_name}",
            category=category,
            url=domain_url,
            base_url=domain_url,
            is_active=True,
            source_type="web",
            scrape_config={},
        )
