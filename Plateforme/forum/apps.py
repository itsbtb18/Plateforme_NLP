from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ForumConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'forum'
    verbose_name = _('Community Forum')

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
