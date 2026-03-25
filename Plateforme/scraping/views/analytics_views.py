"""Analytics view exports."""

from scraping.views_root import (
    _build_duplicate_preview,
    _build_recent_runs_rows,
    _build_skip_reason_payload,
    _build_source_health_rows,
    _map_item_for_duplicate_check,
    analytics,
    duplicates_preview,
    recent_runs,
    skip_reason_analytics,
    source_health_summary,
    trends,
)

__all__ = [
    "analytics",
    "trends",
    "skip_reason_analytics",
    "source_health_summary",
    "recent_runs",
    "duplicates_preview",
    "_build_skip_reason_payload",
    "_build_source_health_rows",
    "_build_recent_runs_rows",
    "_build_duplicate_preview",
    "_map_item_for_duplicate_check",
]
