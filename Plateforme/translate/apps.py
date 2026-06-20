from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class TranslateConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'translate'
    verbose_name = _('Translation Services')
