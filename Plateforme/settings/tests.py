from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import GlobalSettings

User = get_user_model()


class GlobalSettingsTestCase(TestCase):
    """Test cases for GlobalSettings model"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.settings = GlobalSettings.get_settings()
    
    def test_settings_singleton(self):
        """Test that only one GlobalSettings instance can exist"""
        settings1 = GlobalSettings.get_settings()
        settings2 = GlobalSettings.get_settings()
        self.assertEqual(settings1.pk, settings2.pk)
    
    def test_default_settings_values(self):
        """Test that default settings are properly initialized"""
        self.assertEqual(self.settings.site_name, 'NLP Platform')
        self.assertTrue(self.settings.enable_user_registration)
        self.assertTrue(self.settings.enable_email_notifications)
