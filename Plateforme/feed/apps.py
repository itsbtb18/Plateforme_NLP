from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class QaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'feed'
    label = 'QA'
    verbose_name = _('Feed')
