from django.contrib import admin
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from .models import Notification


# ============================================
# ADMIN ACTIONS FOR NOTIFICATIONS
# ============================================

@admin.action(description=_("Mark selected notifications as read"))
def mark_as_read(modeladmin, request, queryset):
    """Admin action to mark notifications as read."""
    updated = queryset.update(read=True)
    messages.success(request, _(f"{updated} notification(s) marked as read."))


@admin.action(description=_("Mark selected notifications as unread"))
def mark_as_unread(modeladmin, request, queryset):
    """Admin action to mark notifications as unread."""
    updated = queryset.update(read=False)
    messages.info(request, _(f"{updated} notification(s) marked as unread."))


@admin.action(description=_("Delete selected notifications"))
def delete_notifications(modeladmin, request, queryset):
    """Admin action to delete notifications."""
    count = queryset.count()
    queryset.delete()
    messages.warning(request, _(f"{count} notification(s) have been deleted."))


# ============================================
# NOTIFICATION ADMIN
# ============================================

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'recipient_email', 'type_badge', 'read_status', 'response_status', 'created_at']
    list_filter = ['type', 'read', 'response_given', 'created_at']
    search_fields = ['title', 'message', 'recipient__email', 'recipient__full_name']
    date_hierarchy = 'created_at'
    actions = [mark_as_read, mark_as_unread, delete_notifications]
    readonly_fields = ['id', 'created_at', 'read_at', 'response_date']
    
    fieldsets = (
        (_('Notification Details'), {
            'fields': ('id', 'title', 'message', 'type')
        }),
        (_('Recipient Information'), {
            'fields': ('recipient',)
        }),
        (_('Status'), {
            'fields': ('read', 'read_at', 'response_given', 'response', 'response_date')
        }),
        (_('Related Object'), {
            'fields': ('content_type', 'object_id', 'project_id', 'sender_id'),
            'classes': ('collapse',),
        }),
        (_('Timestamps'), {
            'fields': ('created_at',)
        }),
    )
    
    def recipient_email(self, obj):
        """Display recipient email."""
        return obj.recipient.email if obj.recipient else '-'
    recipient_email.short_description = _('Recipient')
    recipient_email.admin_order_field = 'recipient__email'
    
    def type_badge(self, obj):
        """Display notification type as a colored badge."""
        colors = {
            'SYSTEM': '#6c757d',
            'PROJECT_INVITATION': '#007bff',
            'MEMBERSHIP_REQUEST': '#17a2b8',
            'PROJECT_UPDATE': '#28a745',
            'TASK_ASSIGNED': '#ffc107',
            'LEAVE_REQUEST': '#dc3545',
            'FOLLOW_REQUEST': '#0ea5e9',
            'COMMENT': '#6610f2',
            'MESSAGE': '#e83e8c',
            'EVENT_CREATED': '#fd7e14',
            'EVENT_APPROVED': '#20c997',
            'RESOURCE_ADDED': '#007bff',
            'TOOL_ADDED': '#6f42c1',
            'CORPUS_UPDATE': '#17a2b8',
            'RESEARCH_UPDATE': '#28a745',
            'FORUM_TOPIC': '#6610f2',
            'QA_ANSWER': '#e83e8c',
            'QA_COMMENT': '#fd7e14',
            'POST_APPROVED': '#20c997',
            'INSTITUTION_UPDATE': '#6c757d',
        }
        color = colors.get(obj.type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_type_display()
        )
    type_badge.short_description = _('Type')
    type_badge.admin_order_field = 'type'
    
    def read_status(self, obj):
        """Display read status as icon."""
        if obj.read:
            return format_html(
                '<span style="color: #28a745;" title="{}"><i class="fas fa-check-circle"></i> {}</span>',
                _('Read'), _('Read')
            )
        return format_html(
            '<span style="color: #ffc107;" title="{}"><i class="fas fa-circle"></i> {}</span>',
            _('Unread'), _('Unread')
        )
    read_status.short_description = _('Status')
    read_status.admin_order_field = 'read'
    
    def response_status(self, obj):
        """Display response status."""
        if not obj.response_given:
            return format_html('<span style="color: #6c757d;">-</span>')
        if obj.response == 'accept':
            return format_html(
                '<span style="color: #28a745;"><i class="fas fa-check"></i> {}</span>',
                _('Accepted')
            )
        elif obj.response == 'reject':
            return format_html(
                '<span style="color: #dc3545;"><i class="fas fa-times"></i> {}</span>',
                _('Rejected')
            )
        return format_html('<span style="color: #6c757d;">-</span>')
    response_status.short_description = _('Response')
    response_status.admin_order_field = 'response'

