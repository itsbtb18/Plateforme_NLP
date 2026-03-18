from django.db import models
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError
from django.conf import settings


class GlobalSettings(models.Model):
    """
    Global platform settings - Singleton pattern
    Only one instance should exist in the database
    """
    
    # ====== PLATFORM CONFIGURATION ======
    site_name = models.CharField(
        max_length=255, 
        default='NLP Platform',
        help_text='Name of the platform'
    )
    site_description = models.TextField(
        blank=True,
        help_text='Description of the platform'
    )
    site_url = models.URLField(
        default='http://localhost:8000',
        help_text='Main URL of the platform'
    )
    logo = models.ImageField(
        upload_to='logos/',
        null=True,
        blank=True,
        help_text='Platform logo'
    )
    favicon = models.ImageField(
        upload_to='favicons/',
        null=True,
        blank=True,
        help_text='Platform favicon'
    )
    
    # ====== EMAIL CONFIGURATION ======
    email_from_name = models.CharField(
        max_length=255,
        default='NLP Platform',
        help_text='Name to display in "From" field of emails'
    )
    email_from_address = models.EmailField(
        default='noreply@nlpplatform.com',
        help_text='Email address to send from'
    )
    smtp_host = models.CharField(
        max_length=255,
        default='smtp.gmail.com',
        help_text='SMTP server host'
    )
    smtp_port = models.IntegerField(
        default=587,
        help_text='SMTP server port'
    )
    smtp_use_tls = models.BooleanField(
        default=True,
        help_text='Use TLS for SMTP connection'
    )
    admin_email = models.EmailField(
        default='admin@nlpplatform.com',
        help_text='Email address to send admin notifications to'
    )
    
    # ====== NOTIFICATION SETTINGS ======
    enable_email_notifications = models.BooleanField(
        default=True,
        help_text='Enable email notifications'
    )
    notify_on_user_registration = models.BooleanField(
        default=True,
        help_text='Send notification when new user registers'
    )
    notify_on_resource_submission = models.BooleanField(
        default=True,
        help_text='Send notification when new resource is submitted'
    )
    notify_on_forum_post = models.BooleanField(
        default=True,
        help_text='Send notification on new forum posts'
    )
    notify_on_event = models.BooleanField(
        default=True,
        help_text='Send notification for new events'
    )
    notification_email = models.EmailField(
        default='notifications@nlpplatform.com',
        help_text='Email to send notification alerts to'
    )
    
    # ====== FEATURE FLAGS ======
    enable_user_registration = models.BooleanField(
        default=True,
        help_text='Allow new user registrations'
    )
    enable_social_login = models.BooleanField(
        default=True,
        help_text='Enable social login (Google, etc.)'
    )
    enable_two_factor_auth = models.BooleanField(
        default=True,
        help_text='Enable two-factor authentication'
    )
    enable_forum = models.BooleanField(
        default=True,
        help_text='Enable forum functionality'
    )
    enable_qa = models.BooleanField(
        default=True,
        help_text='Enable Q&A functionality'
    )
    enable_events = models.BooleanField(
        default=True,
        help_text='Enable events functionality'
    )
    enable_projects = models.BooleanField(
        default=True,
        help_text='Enable projects functionality'
    )
    enable_chatbot = models.BooleanField(
        default=True,
        help_text='Enable chatbot functionality'
    )
    enable_resource_submission = models.BooleanField(
        default=True,
        help_text='Allow users to submit resources'
    )
    enable_resource_approval = models.BooleanField(
        default=True,
        help_text='Require approval for submitted resources'
    )
    
    # ====== CONTENT MODERATION ======
    enable_content_moderation = models.BooleanField(
        default=True,
        help_text='Enable content moderation features'
    )
    max_upload_size_mb = models.IntegerField(
        default=50,
        help_text='Maximum file upload size in MB'
    )
    require_email_verification = models.BooleanField(
        default=True,
        help_text='Require email verification for registration'
    )
    
    # ====== MAINTENANCE ======
    maintenance_mode = models.BooleanField(
        default=False,
        help_text='Enable maintenance mode (site unavailable to public)'
    )
    maintenance_message = models.TextField(
        blank=True,
        help_text='Message to display during maintenance'
    )
    
    # ====== METADATA ======
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='settings_updates'
    )
    
    class Meta:
        verbose_name = 'Global Settings'
        verbose_name_plural = 'Global Settings'
    
    def __str__(self):
        return f'{self.site_name} - Settings'
    
    def save(self, *args, **kwargs):
        # Enforce singleton pattern
        if not self.pk and GlobalSettings.objects.exists():
            self.pk = GlobalSettings.objects.first().pk
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create the global settings instance"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
