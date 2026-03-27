from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ScrapingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "scraping"
    verbose_name = _("Web Scraping")

    def ready(self):
        # Register model signals (post_save auto-validation hooks).
        import scraping.signals  # noqa: F401
