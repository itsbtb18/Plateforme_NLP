import logging

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


def verify_category_models() -> None:
    """Verify that canonical categories resolve to configured model classes."""
    from django.apps import apps

    from scraping.constants import CANONICAL_CATEGORIES, CATEGORY_META

    for category in CANONICAL_CATEGORIES:
        meta = CATEGORY_META.get(category, {})
        app_label = meta.get("model_app")
        model_name = meta.get("model_name")

        if not app_label or not model_name:
            continue

        try:
            apps.get_model(app_label, model_name)
            logger.info(
                "Category model OK: %s -> %s.%s", category, app_label, model_name
            )
        except LookupError:
            logger.error(
                "CRITICAL category model missing: %s -> %s.%s",
                category,
                app_label,
                model_name,
            )


class ScrapingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "scraping"
    verbose_name = _("Web Scraping")

    def ready(self):
        # Register model signals (post_save auto-validation hooks).
        import scraping.signals  # noqa: F401

        verify_category_models()
