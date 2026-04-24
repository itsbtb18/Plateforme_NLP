from django.contrib import admin
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from events.models import Event, EventRegistration
from Plateforme.admin_forms import EventAdminForm


# ============================================
# ADMIN ACTIONS FOR APPROVAL WORKFLOW
# ============================================

@admin.action(description=_("Approve selected events"))
def approve_events(modeladmin, request, queryset):
    """Admin action to approve selected events."""
    updated = queryset.update(approval_status='approved', is_approved=True)
    messages.success(request, _(f"{updated} event(s) have been approved."))


@admin.action(description=_("Reject and delete selected events"))
def reject_events(modeladmin, request, queryset):
    """Admin action to reject and delete selected events."""
    count = queryset.count()
    queryset.delete()
    messages.warning(request, _(f"{count} event(s) have been rejected and deleted."))


@admin.action(description=_("Mark as pending review"))
def mark_events_pending(modeladmin, request, queryset):
    """Admin action to mark events as pending."""
    updated = queryset.update(approval_status='pending', is_approved=False)
    messages.info(request, _(f"{updated} event(s) marked as pending."))


# ============================================
# EVENT ADMIN
# ============================================

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    form = EventAdminForm
    list_display = ('title', 'event_type', 'start_date', 'end_date', 'approval_status_badge', 'is_upcoming')
    list_filter = ('approval_status', 'event_type', 'is_approved', 'start_date', 'domains')
    search_fields = ('title', 'title_ar', 'title_en', 'description', 'organizer__name')
    date_hierarchy = 'start_date'
    actions = [approve_events, reject_events, mark_events_pending]
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'event_type', 'domains', 'location', 
                      'start_date', 'end_date', 'submission_deadline', 'website', 
                      'organizer', 'contact_email', 'attachment', 'created_by')
        }),
        (_('Translation Fields (Admin fills before approval)'), {
            'fields': ('title_ar', 'title_en', 'description_ar', 'description_en', 'location_ar', 'location_en'),
            'classes': ('collapse',),
            'description': _('Fill in the Arabic and English translations before approving.')
        }),
        (_('Approval Status'), {
            'fields': ('approval_status', 'is_approved'),
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
# PENDING EVENT PROXY MODEL & ADMIN
# ============================================

class PendingEvent(Event):
    """Proxy model to show only pending events in admin."""
    class Meta:
        proxy = True
        verbose_name = _('Pending Event')
        verbose_name_plural = _('Pending Events')


@admin.register(PendingEvent)
class PendingEventAdmin(EventAdmin):
    """Admin view showing only pending events for review."""
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(approval_status='pending')
    
    def has_add_permission(self, request):
        return False


# ============================================
# EVENT REGISTRATION ADMIN
# ============================================

@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'registration_date')
    list_filter = ('registration_date',)
    search_fields = ('user__email', 'event__title')

