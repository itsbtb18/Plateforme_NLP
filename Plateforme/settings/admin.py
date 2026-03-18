from django.contrib import admin
from django.utils.html import format_html
from .models import GlobalSettings


@admin.register(GlobalSettings)
class GlobalSettingsAdmin(admin.ModelAdmin):
    """
    Admin interface for global platform settings
    Organized in logical fieldsets for better UX
    """
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of global settings"""
        return False
    
    def has_add_permission(self, request):
        """Prevent creation of multiple settings instances"""
        return not GlobalSettings.objects.exists()
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Customize the change view"""
        extra_context = extra_context or {}
        extra_context['title'] = 'Edit Global Platform Settings'
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context,
        )
    
    fieldsets = (
        ('📱 Platform Information', {
            'description': 'Basic platform identification and branding',
            'fields': ('site_name', 'site_description', 'site_url', 'logo', 'favicon')
        }),
        ('📧 Email Configuration', {
            'description': 'Configure email settings for outgoing emails',
            'fields': (
                'email_from_name',
                'email_from_address',
                'smtp_host',
                'smtp_port',
                'smtp_use_tls',
                'admin_email',
            ),
            'classes': ('collapse',),
        }),
        ('🔔 Notification Settings', {
            'description': 'Configure which notifications are enabled',
            'fields': (
                'enable_email_notifications',
                'notify_on_user_registration',
                'notify_on_resource_submission',
                'notify_on_forum_post',
                'notify_on_event',
                'notification_email',
            ),
        }),
        ('⚙️ Feature Flags', {
            'description': 'Enable or disable specific platform features',
            'fields': (
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
            ),
        }),
        ('🛡️ Content Moderation & Security', {
            'description': 'Security and content moderation settings',
            'fields': (
                'enable_content_moderation',
                'max_upload_size_mb',
                'require_email_verification',
            ),
        }),
        ('🔧 Maintenance', {
            'description': 'Maintenance mode for site updates',
            'fields': ('maintenance_mode', 'maintenance_message'),
            'classes': ('collapse',),
        }),
        ('ℹ️ Metadata', {
            'description': 'Last update information',
            'fields': ('updated_at', 'updated_by'),
        }),
    )
    
    readonly_fields = ('updated_at', 'updated_by')
    
    def save_model(self, request, obj, form, change):
        """Track who updated the settings"""
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_list_display(self, request):
        """Customize list display"""
        return ['site_name', 'get_status_indicator', 'updated_at']
    
    def get_status_indicator(self, obj):
        """Show visual indicator for maintenance mode"""
        if obj.maintenance_mode:
            return format_html(
                '<span style="color: red; font-weight: bold;">🔴 Maintenance Mode</span>'
            )
        return format_html(
            '<span style="color: green; font-weight: bold;">🟢 Active</span>'
        )
    get_status_indicator.short_description = 'Status'
