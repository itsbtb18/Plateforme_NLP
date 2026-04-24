"""Compatibility shim for deprecated split scraping.views package."""

# DEPRECATED: import from scraping.views_root instead.
from scraping.views_root import *  # noqa: F401,F403

# Keep private helper re-exports for backward compatibility.
from scraping.views_root import (  # noqa: F401
    _build_duplicate_preview,
    _build_recent_runs_rows,
    _build_skip_reason_payload,
    _build_source_health_rows,
    _client_ip,
    _enforce_rate_limit,
    _infer_source_tier,
    _log_scraping_action,
    _map_item_for_duplicate_check,
    _model_for_category,
    _require_json_content_type,
    _require_staff,
    _run_source_test_job,
)

# Historical placeholder from the split package.
_media_stats = None
