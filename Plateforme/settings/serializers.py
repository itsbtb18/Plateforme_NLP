"""
Serializers for the settings app
Used for API endpoints and data validation
"""
from rest_framework import serializers
from .models import GlobalSettings


class GlobalSettingsSerializer(serializers.ModelSerializer):
    """Serializer for GlobalSettings model"""
    
    updated_by_username = serializers.CharField(
        source='updated_by.username',
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        model = GlobalSettings
        fields = [
            # Platform Information
            'id',
            'site_name',
            'site_description',
            'site_url',
            'logo',
            'favicon',
            
            # Email Configuration
            'email_from_name',
            'email_from_address',
            'smtp_host',
            'smtp_port',
            'smtp_use_tls',
            'admin_email',
            
            # Notifications
            'enable_email_notifications',
            'notify_on_user_registration',
            'notify_on_resource_submission',
            'notify_on_forum_post',
            'notify_on_event',
            'notification_email',
            
            # Feature Flags
            'enable_user_registration',
            'enable_social_login',
            'enable_two_factor_auth',
            'enable_forum',
            'enable_qa',
            'enable_events',
            'enable_projects',
            'enable_chatbot',
            'enable_resource_submission',
            'enable_resource_approval',
            
            # Moderation
            'enable_content_moderation',
            'max_upload_size_mb',
            'require_email_verification',
            
            # Maintenance
            'maintenance_mode',
            'maintenance_message',
            
            # Metadata
            'updated_at',
            'updated_by_username',
        ]
        read_only_fields = ['updated_at', 'updated_by_username']
