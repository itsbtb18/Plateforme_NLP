from django.apps import AppConfig


class SettingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'settings'
    verbose_name = 'Platform Settings'
    
    def ready(self):
        from .signals import connect_signals
        connect_signals()
