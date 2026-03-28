"""Prometheus metrics for scraping observability."""

import time

from django.db.models import Max
from django.utils import timezone
from prometheus_client import Counter, Gauge, Histogram

from .constants import DEDUP_RULE_UNKNOWN
from .scraping_settings import scraping_settings as SS

scrape_runs_total = Counter(
    "scrape_runs_total",
    "Total number of scraping runs by category and status.",
    ["category", "status"],
)

scrape_duration_seconds = Histogram(
    "scrape_duration_seconds",
    "Scraping run duration in seconds by category.",
    ["category"],
    buckets=SS.METRICS_SCRAPE_DURATION_BUCKETS,
)

scrape_items_total = Counter(
    "scrape_items_total",
    "Total scraped items by category and outcome.",
    ["category", "outcome"],
)

scraping_render_method_total = Counter(
    "scraping_render_method_total",
    "Total page fetches by render method.",
    ["method"],
)

scraping_playwright_fallback_total = Counter(
    "scraping_playwright_fallback_total",
    "Number of times Playwright was used as fallback",
    ["domain", "reason"],
)

scraping_network_failures_total = Counter(
    "scraping_network_failures_total",
    "Network failures by type and domain",
    ["error_type", "domain"],
)

scraping_circuit_breaker_trips_total = Counter(
    "scraping_circuit_breaker_trips_total",
    "Circuit breaker activations by domain",
    ["domain"],
)

scraping_sites_skipped_total = Counter(
    "scraping_sites_skipped_total",
    "Total sites skipped due to unreachable/network errors.",
    ["reason"],
)

scraping_wayback_fallback_total = Counter(
    "scraping_wayback_fallback_total",
    "Items recovered via Wayback Machine",
    ["domain", "result"],
)

scrape_source_duration_seconds = Histogram(
    "scrape_source_duration_seconds",
    "Source-level scraping duration in seconds.",
    ["category", "source_name", "source_tier"],
    buckets=SS.METRICS_SOURCE_DURATION_BUCKETS,
)

scrape_source_items_total = Counter(
    "scrape_source_items_total",
    "Source-level scraped item outcomes.",
    ["category", "source_name", "outcome"],
)

scrape_dedup_hits_total = Counter(
    "scrape_dedup_hits_total",
    "Dedup hits by category and rule.",
    ["category", "dedup_rule"],
)

file_download_total = Counter(
    "file_download_total",
    "File download outcomes.",
    ["category", "file_type", "outcome"],
)

file_download_bytes_total = Counter(
    "file_download_bytes_total",
    "Downloaded file bytes.",
    ["category", "file_type"],
)

enrichment_duration_seconds = Histogram(
    "enrichment_duration_seconds",
    "Enrichment step duration in seconds.",
    ["category", "enrichment_step"],
    buckets=SS.METRICS_ENRICHMENT_DURATION_BUCKETS,
)

enrichment_failures_total = Counter(
    "enrichment_failures_total",
    "Enrichment step failures.",
    ["category", "enrichment_step", "failure_reason"],
)

source_health_score = Gauge(
    "source_health_score",
    "Current source health score (0-100).",
    ["source_url"],
)

circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state as one-hot gauge (1 active, 0 inactive).",
    ["source_url", "state"],
)

source_health_state = Gauge(
    "source_health_state",
    "Source health state as one-hot gauge.",
    ["source_url", "state"],
)

scrape_queue_lag_seconds = Gauge(
    "scrape_queue_lag_seconds",
    "Current queue lag as now minus latest completed run start time.",
    ["category"],
)

_last_queue_lag_update_monotonic = 0.0


def _normalize_dedup_rule(skip_reason: str) -> str:
    mapping = {
        "dedup_url": "url_exact",
        "dedup_name": "name_exact",
        "dedup_similarity": "similarity",
        "dedup_embedding": "embedding",
        "dedup_doi": "url_exact",
        "dedup_arxiv": "url_exact",
        "dedup_ror": "url_exact",
    }
    return mapping.get((skip_reason or "").strip(), DEDUP_RULE_UNKNOWN)


def record_skip_reason(category: str, skip_reason: str, source_name: str = "unknown"):
    """Emit counters for skip reasons and dedup hits."""
    category_value = (category or "unknown").strip() or "unknown"
    source_value = (source_name or "unknown").strip() or "unknown"
    reason = (skip_reason or "").strip()
    if not reason:
        return

    is_dedup = reason.startswith("dedup_")
    outcome = "skipped_dedup" if is_dedup else "skipped_error"
    scrape_source_items_total.labels(
        category=category_value,
        source_name=source_value,
        outcome=outcome,
    ).inc()

    if is_dedup:
        scrape_dedup_hits_total.labels(
            category=category_value,
            dedup_rule=_normalize_dedup_rule(reason),
        ).inc()


def update_source_health_metrics(category=None):
    """Sync source health and circuit breaker gauges from DB rows."""
    from scraping.models import ScrapingSourceHealth

    qs = ScrapingSourceHealth.objects.all()
    if category:
        qs = qs.filter(category=category)

    states = ("closed", "open", "half_open")

    for health in qs.iterator():
        source_url = health.base_url or health.source_name
        source_health_score.labels(source_url=source_url).set(
            float(health.health_score)
        )

        for state in states:
            is_current = 1.0 if health.circuit_state == state else 0.0
            circuit_breaker_state.labels(source_url=source_url, state=state).set(
                is_current
            )
            source_health_state.labels(source_url=source_url, state=state).set(
                is_current
            )


def update_scrape_queue_lag_metrics(
    min_interval_seconds: int = SS.METRICS_LAG_INTERVAL, force: bool = False
):
    """Update queue lag gauge, throttled to once per minute by default."""
    global _last_queue_lag_update_monotonic

    now_mono = time.monotonic()
    if (
        not force
        and (now_mono - _last_queue_lag_update_monotonic) < min_interval_seconds
    ):
        return
    _last_queue_lag_update_monotonic = now_mono

    from scraping.models import ScrapingRun
    from scraping.scrapers import CATEGORY_META

    now = timezone.now()

    rows = (
        ScrapingRun.objects.filter(status="completed")
        .values("category")
        .annotate(last_started=Max("started_at"))
    )
    by_category = {row["category"]: row["last_started"] for row in rows}

    for category in CATEGORY_META:
        started = by_category.get(category)
        lag = (now - started).total_seconds() if started else 0.0
        scrape_queue_lag_seconds.labels(category=category).set(max(0.0, float(lag)))
