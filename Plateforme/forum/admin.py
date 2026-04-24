from django.contrib import admin
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from .models import Topic, ChatRoom, Message
from Plateforme.admin_forms import TopicAdminForm


# ============================================
# ADMIN ACTIONS FOR APPROVAL WORKFLOW
# ============================================

@admin.action(description=_("Approve selected topics"))
def approve_topics(modeladmin, request, queryset):
    """Admin action to approve selected topics."""
    updated = queryset.update(approval_status='approved')
    messages.success(request, _(f"{updated} topic(s) have been approved."))


@admin.action(description=_("Reject and delete selected topics"))
def reject_topics(modeladmin, request, queryset):
    """Admin action to reject and delete selected topics."""
    count = queryset.count()
    queryset.delete()
    messages.warning(request, _(f"{count} topic(s) have been rejected and deleted."))


@admin.action(description=_("Mark as pending review"))
def mark_topics_pending(modeladmin, request, queryset):
    """Admin action to mark topics as pending."""
    updated = queryset.update(approval_status='pending')
    messages.info(request, _(f"{updated} topic(s) marked as pending."))


# ============================================
# TOPIC ADMIN
# ============================================

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    form = TopicAdminForm
    list_display = ['title', 'creator', 'approval_status_badge', 'is_closed', 'created_at']
    list_filter = ['approval_status', 'is_closed', 'created_at']
    search_fields = ['title', 'title_ar', 'title_en', 'description', 'creator__email']
    date_hierarchy = 'created_at'
    actions = [approve_topics, reject_topics, mark_topics_pending]
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'creator', 'is_closed')
        }),
        (_('Translation Fields (Admin fills before approval)'), {
            'fields': ('title_ar', 'title_en', 'description_ar', 'description_en'),
            'classes': ('collapse',),
            'description': _('Fill in the Arabic and English translations before approving.')
        }),
        (_('Approval Status'), {
            'fields': ('approval_status',),
            'classes': ('wide',),
        }),
    )
    
    def approval_status_badge(self, obj):
        """Display approval status as a colored badge."""
        colors = {
            'pending': '#ffc107',
            'approved': '#28a745', 
            'rejected': '#dc3545',
        }
        color = colors.get(obj.approval_status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_approval_status_display()
        )
    approval_status_badge.short_description = _('Approval Status')
    approval_status_badge.admin_order_field = 'approval_status'


# ============================================
# PENDING TOPIC PROXY MODEL & ADMIN
# ============================================

class PendingTopic(Topic):
    """Proxy model to show only pending topics in admin."""
    class Meta:
        proxy = True
        verbose_name = _('Pending Topic')
        verbose_name_plural = _('Pending Topics')


@admin.register(PendingTopic)
class PendingTopicAdmin(TopicAdmin):
    """Admin view showing only pending topics for review."""
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(approval_status='pending')
    
    def has_add_permission(self, request):
        return False


# ============================================
# CHAT ROOM & MESSAGE ADMIN
# ============================================

@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'topic', 'creator', 'created_at']
    list_filter = ['topic', 'created_at']
    search_fields = ['name', 'description', 'topic__title']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['chatroom', 'user', 'content_preview', 'timestamp', 'is_edited']
    list_filter = ['chatroom', 'is_edited', 'timestamp']
    search_fields = ['content', 'user__email']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = _('Content')



