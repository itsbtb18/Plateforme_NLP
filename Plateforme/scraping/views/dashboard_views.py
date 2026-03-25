"""Dashboard-related view exports."""

from scraping.views_root import _infer_source_tier, _model_for_category, dashboard

# _media_stats is a nested helper inside dashboard in the legacy module.
# Exported as optional symbol for split structure completeness.
_media_stats = None

__all__ = ["dashboard", "_media_stats", "_infer_source_tier", "_model_for_category"]
