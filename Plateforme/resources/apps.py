from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import logging


logger = logging.getLogger(__name__)


class ResourcesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'resources'
    verbose_name = _('Resources & Publications')

    def ready(self):
        # Import signal module to register decorated handlers.
        from django.apps import apps
        from django.db.models.signals import post_save

        try:
            from . import signals
        except ImportError:
            logger.exception("Failed to import resources.signals during app ready()")
            if settings.DEBUG:
                raise
            return

        # Optional hook: connect contribution handler only if the model exists.
        try:
            contribution_model = apps.get_model("resources", "ResourceContribution")
        except LookupError:
            contribution_model = None

        if contribution_model is not None:
            post_save.connect(
                signals.notify_resource_contribution,
                sender=contribution_model,
                dispatch_uid="resources.notify_resource_contribution",
            )
