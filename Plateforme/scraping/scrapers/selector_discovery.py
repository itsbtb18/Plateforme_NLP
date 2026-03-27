"""Automatic CSS selector discovery engine for new scraping domains.

The scoring strategy is inspired by ACA/APA-style adaptive extraction:
- evaluate multiple selector candidates across several sample pages
- reward stable selectors that occur frequently
- reward selectors that extract meaningful content
- reward selectors with useful structural specificity
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

CANDIDATE_PATTERNS: dict[str, list[str]] = {
    "title": [
        "h1",
        "h1.entry-title",
        "h1.post-title",
        "h1.article-title",
        ".article-title",
        ".post-title",
        ".entry-title",
        ".news-title",
        '[itemprop="headline"]',
        'meta[property="og:title"]',
        ".title h1",
        "article h1",
        "main h1",
    ],
    "summary": [
        ".article-body",
        ".entry-content",
        ".post-content",
        ".content",
        '[itemprop="description"]',
        ".summary",
        ".excerpt",
        ".lead",
        "article p",
        ".news-content",
        ".description",
        "main article",
    ],
    "date": [
        '[itemprop="datePublished"]',
        "time[datetime]",
        ".published-date",
        ".post-date",
        ".article-date",
        ".date",
        'meta[property="article:published_time"]',
        ".entry-date",
        ".news-date",
        "time.entry-date",
    ],
    "author": [
        '[itemprop="author"]',
        ".author",
        ".byline",
        ".post-author",
        ".article-author",
        'meta[name="author"]',
        ".writer",
        ".by-author",
    ],
}


@dataclass
class SelectorScore:
    hits: int = 0
    total_length: int = 0
    specificity_sum: float = 0.0
    sample_texts: list[str] | None = None

    def __post_init__(self):
        if self.sample_texts is None:
            self.sample_texts = []


class SelectorDiscoveryEngine:
    def __init__(
        self,
        min_content_length: int = 50,
        min_occurrence_ratio: float = 0.3,
        request_timeout: tuple[float, float] = (3, 7),
        user_agent: str | None = None,
    ):
        self.min_content_length = int(min_content_length)
        self.min_occurrence_ratio = float(min_occurrence_ratio)
        self.request_timeout = request_timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (compatible; SelectorDiscoveryBot/1.0; +https://example.local)"
        )
        self._last_sample_count = 0

    def discover(
        self, domain_url: str, sample_urls: list[str] | None = None
    ) -> dict[str, Any]:
        """Discover and rank CSS selectors for a domain.

        Crawls sample pages and returns top-ranked selectors per extraction field.
        """
        if not sample_urls:
            sample_urls = self._discover_sample_urls(domain_url, count=5)

        if not sample_urls:
            raise ValueError("No suitable sample URLs discovered for selector analysis")

        scores = self._score_patterns(sample_urls)
        recommendations = self._get_top_recommendations(scores)

        return {
            "domain": domain_url,
            "sample_count": len(sample_urls),
            "sample_urls": sample_urls,
            "recommendations": recommendations,
            "confidence": self._compute_confidence(scores),
        }

    def _http_get(self, url: str) -> requests.Response:
        return requests.get(
            url,
            timeout=self.request_timeout,
            headers={"User-Agent": self.user_agent},
            allow_redirects=True,
        )

    def _discover_sample_urls(self, domain_url: str, count: int) -> list[str]:
        """Crawl homepage and return candidate internal content URLs."""
        response = self._http_get(domain_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        base = urlparse(domain_url)

        links: list[str] = []
        ignored_suffixes = (
            ".css",
            ".js",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".svg",
            ".webp",
            ".pdf",
            ".zip",
        )

        for anchor in soup.find_all("a", href=True):
            href = urljoin(domain_url, anchor["href"])
            parsed = urlparse(href)
            if parsed.netloc != base.netloc:
                continue
            if len(parsed.path or "") <= 10:
                continue
            if (parsed.path or "").lower().endswith(ignored_suffixes):
                continue
            links.append(href)

        return list(dict.fromkeys(links))[: int(count)]

    def _extract_element_text(self, soup: BeautifulSoup, pattern: str) -> str:
        element = soup.select_one(pattern)
        if not element:
            return ""

        if element.name == "meta":
            return (element.get("content") or "").strip()

        return element.get_text(" ", strip=True)

    def _min_length_for_field(self, field: str) -> int:
        # Dates and authors are naturally short; keep threshold practical.
        if field == "date":
            return min(self.min_content_length, 8)
        if field == "author":
            return min(self.min_content_length, 3)
        return self.min_content_length

    def _selector_specificity(self, pattern: str) -> float:
        # Approximate selector specificity normalized to [0, 1].
        ids = pattern.count("#")
        classes = pattern.count(".") + pattern.count("[")
        descendants = max(pattern.count(" "), 0)
        tags = sum(
            1
            for token in pattern.replace(">", " ").split()
            if token and token[0].isalpha()
        )

        raw = (ids * 0.45) + (classes * 0.22) + (descendants * 0.1) + (tags * 0.08)
        return min(raw, 1.0)

    def _score_patterns(
        self, sample_urls: list[str]
    ) -> dict[str, dict[str, SelectorScore]]:
        field_scores: dict[str, dict[str, SelectorScore]] = {
            field: {} for field in CANDIDATE_PATTERNS
        }
        self._last_sample_count = len(sample_urls)

        for url in sample_urls:
            try:
                response = self._http_get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")
            except Exception as exc:
                logger.warning(
                    "selector_discovery_sample_fetch_failed url=%s err=%s", url, exc
                )
                continue

            for field, patterns in CANDIDATE_PATTERNS.items():
                min_len = self._min_length_for_field(field)
                for pattern in patterns:
                    text = self._extract_element_text(soup, pattern)
                    if len(text) < min_len:
                        continue

                    score = field_scores[field].setdefault(pattern, SelectorScore())
                    score.hits += 1
                    score.total_length += len(text)
                    score.specificity_sum += self._selector_specificity(pattern)
                    if len(score.sample_texts) < 3:
                        score.sample_texts.append(text[:100])

        return field_scores

    def _rank_pattern(
        self,
        pattern: str,
        score: SelectorScore,
        total_samples: int,
    ) -> dict[str, Any]:
        occurrence_ratio = score.hits / max(total_samples, 1)
        avg_length = score.total_length / max(score.hits, 1)
        avg_specificity = score.specificity_sum / max(score.hits, 1)

        # Composite score inspired by ACA/APA style adaptive ranking.
        composite = (
            (occurrence_ratio * 0.55)
            + (min(avg_length / 500, 1.0) * 0.30)
            + (avg_specificity * 0.15)
        )

        return {
            "selector": pattern,
            "score": round(composite, 3),
            "occurrence_ratio": round(occurrence_ratio, 2),
            "avg_content_length": round(avg_length),
            "specificity": round(avg_specificity, 2),
            "sample_texts": score.sample_texts[:2],
        }

    def _get_top_recommendations(
        self,
        scores: dict[str, dict[str, SelectorScore]],
        top_n: int = 3,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return top selectors per field ranked by composite score."""
        recommendations: dict[str, list[dict[str, Any]]] = {}
        total_samples = self._last_sample_count or 5

        for field, pattern_scores in scores.items():
            ranked: list[dict[str, Any]] = []
            for pattern, data in pattern_scores.items():
                occurrence_ratio = data.hits / max(total_samples, 1)
                if occurrence_ratio < self.min_occurrence_ratio:
                    continue
                ranked.append(self._rank_pattern(pattern, data, total_samples))

            ranked.sort(key=lambda item: item["score"], reverse=True)
            recommendations[field] = ranked[:top_n]

        return recommendations

    def _compute_confidence(self, scores: dict[str, dict[str, SelectorScore]]) -> float:
        """Compute global confidence [0, 1] from top scores and field coverage."""
        top_scores: list[float] = []
        covered_fields = 0

        for field_scores in scores.values():
            if not field_scores:
                continue

            covered_fields += 1
            ranked = [
                self._rank_pattern(pattern, data, max(self._last_sample_count, 1))[
                    "score"
                ]
                for pattern, data in field_scores.items()
            ]
            if ranked:
                top_scores.append(max(ranked))

        if not top_scores:
            return 0.0

        score_strength = sum(top_scores) / len(top_scores)
        field_coverage = covered_fields / max(len(CANDIDATE_PATTERNS), 1)
        confidence = (score_strength * 0.7) + (field_coverage * 0.3)
        return max(0.0, min(round(confidence, 3), 1.0))
