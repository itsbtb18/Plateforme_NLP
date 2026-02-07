from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    
    def ready(self):
        """
        Import signals when app is ready
        """
        try:
            from . import two_factor_auth  # noqa: F401
            logger.info("✅ 2FA signals registered successfully")
        except ImportError as e:
            logger.error(f"❌ Failed to import 2FA signals: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error importing 2FA signals: {str(e)}")

