from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from pages.moderation import ModerationMixin
from .models import Question, Answer, Comment, Post


@admin.action(description=_("Approve Selected Posts"))
def approve_posts(modeladmin, request, queryset):
    """Mark selected posts as approved."""
    updated = queryset.update(approval_status='approved')
    modeladmin.message_user(request, _("%(count)d post(s) successfully approved.") % {'count': updated})


@admin.action(description=_("Reject Selected Posts"))
def reject_posts(modeladmin, request, queryset):
    """Mark selected posts as rejected."""
    updated = queryset.update(approval_status='rejected')
    modeladmin.message_user(request, _("%(count)d post(s) rejected.") % {'count': updated})


@admin.action(description=_("Mark as Pending"))
def mark_pending(modeladmin, request, queryset):
    """Mark selected posts as pending review."""
    updated = queryset.update(approval_status='pending')
    modeladmin.message_user(request, _("%(count)d post(s) marked as pending.") % {'count': updated})


@admin.register(Post)
class PostAdmin(ModerationMixin, admin.ModelAdmin):
    list_display = ('get_title', 'author', 'approval_status', 'created_at', 'total_likes', 'total_comments')
    list_filter = ('approval_status', 'created_at', 'author')
    list_editable = ('approval_status',)
    search_fields = ('title', 'title_ar', 'title_en', 'content', 'author__email', 'author__full_name')
    readonly_fields = ('id', 'slug', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    actions = [*ModerationMixin.actions, mark_pending]
    
    fieldsets = (
        (None, {
            'fields': ('author', 'approval_status')
        }),
        (_('Title'), {
            'fields': ('title', 'title_ar', 'title_en')
        }),
        (_('Content'), {
            'fields': ('content', 'content_ar', 'content_en')
        }),
        (_('Media'), {
            'fields': ('image', 'file')
        }),
        (_('Metadata'), {
            'fields': ('id', 'slug', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description=_('Title'))
    def get_title(self, obj):
        return obj.get_localized_title() or f"Post {obj.id}"


admin.site.register(Question)
admin.site.register(Answer)
admin.site.register(Comment)

