from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import logging


logger = logging.getLogger(__name__)


class ForumConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'forum'
    verbose_name = _('Community Forum')

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except ImportError:
            logger.exception("Failed to import forum.signals during app ready()")
            if settings.DEBUG:
                raise
