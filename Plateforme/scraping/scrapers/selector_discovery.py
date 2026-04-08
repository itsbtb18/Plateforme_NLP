"""Automatic CSS selector recommendation without live HTTP crawling."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

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


_FIELD_HINTS: dict[str, tuple[str, ...]] = {
    "title": ("event", "news", "article", "post", "course", "tool"),
    "summary": ("blog", "news", "article", "resource", "about"),
    "date": ("event", "news", "archive", "post"),
    "author": ("blog", "news", "article", "team"),
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
        self.user_agent = user_agent or "SelectorDiscoveryBot/2.0"
        self._last_sample_count = 0

    def discover(
        self, domain_url: str, sample_urls: list[str] | None = None
    ) -> dict[str, Any]:
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

    def _discover_sample_urls(self, domain_url: str, count: int) -> list[str]:
        parsed = urlparse(domain_url)
        if not parsed.scheme:
            domain_url = f"https://{domain_url}"
            parsed = urlparse(domain_url)

        base = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        candidates = [
            "/events",
            "/news",
            "/blog",
            "/articles",
            "/resources",
            "/courses",
            "/tools",
            "/about",
        ]

        urls = []
        for path in candidates:
            urls.append(urljoin(base + "/", path.lstrip("/")))

        deduped = []
        seen = set()
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            deduped.append(url)
            if len(deduped) >= int(count):
                break

        return deduped

    def _min_length_for_field(self, field: str) -> int:
        if field == "date":
            return min(self.min_content_length, 8)
        if field == "author":
            return min(self.min_content_length, 3)
        return self.min_content_length

    def _selector_specificity(self, pattern: str) -> float:
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
            lowered_url = (url or "").lower()
            for field, patterns in CANDIDATE_PATTERNS.items():
                hints = _FIELD_HINTS.get(field, ())
                field_signal = 1 if any(token in lowered_url for token in hints) else 0
                min_len = self._min_length_for_field(field)

                for index, pattern in enumerate(patterns):
                    score = field_scores[field].setdefault(pattern, SelectorScore())
                    base_hit = 1 if index < 4 else 0
                    if field_signal or base_hit:
                        score.hits += 1
                        pseudo_len = max(min_len, 120 - (index * 7))
                        score.total_length += pseudo_len
                        score.specificity_sum += self._selector_specificity(pattern)
                        if len(score.sample_texts) < 3:
                            score.sample_texts.append(f"signal:{url}")

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
        recommendations: dict[str, list[dict[str, Any]]] = {}
        total_samples = self._last_sample_count or 1

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
        top_scores: list[float] = []
        covered_fields = 0

        for field_scores in scores.values():
            if not field_scores:
                continue

            covered_fields += 1
            ranked = [
                self._rank_pattern(pattern, data, max(self._last_sample_count, 1))["score"]
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
