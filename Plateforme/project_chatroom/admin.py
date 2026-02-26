from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import ProjectChat, ProjectChatMessage, ProjectChatFileAttachment


@admin.register(ProjectChat)
class ProjectChatAdmin(admin.ModelAdmin):
    list_display = ['project', 'message_count', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['project__title']
    readonly_fields = ['id', 'created_at', 'updated_at']

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = _('Messages')

    def has_add_permission(self, request):
        # Prevent manual creation; chats are auto-created when projects are created
        return False

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion through admin
        return False


@admin.register(ProjectChatMessage)
class ProjectChatMessageAdmin(admin.ModelAdmin):
    list_display = ['author', 'chat', 'short_content', 'created_at', 'is_edited']
    list_filter = ['created_at', 'is_edited', 'chat__project']
    search_fields = ['author__full_name', 'author__email', 'content', 'chat__project__title']
    readonly_fields = ['id', 'created_at', 'updated_at', 'author']
    date_hierarchy = 'created_at'

    fieldsets = (
        (None, {
            'fields': ('id', 'chat', 'author', 'content', 'is_edited')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def short_content(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    short_content.short_description = _('Content')

    def has_add_permission(self, request):
        return False


@admin.register(ProjectChatFileAttachment)
class ProjectChatFileAttachmentAdmin(admin.ModelAdmin):
    list_display = ['original_filename', 'attachment_type', 'uploaded_by', 'file_size_kb', 'uploaded_at']
    list_filter = ['attachment_type', 'uploaded_at', 'message__chat__project']
    search_fields = ['original_filename', 'uploaded_by__full_name', 'uploaded_by__email']
    readonly_fields = ['id', 'uploaded_at', 'message', 'uploaded_by', 'file']
    date_hierarchy = 'uploaded_at'

    fieldsets = (
        (None, {
            'fields': ('id', 'message', 'file', 'original_filename', 'attachment_type')
        }),
        (_('Details'), {
            'fields': ('file_size', 'uploaded_by', 'uploaded_at')
        }),
    )

    def file_size_kb(self, obj):
        return f"{obj.file_size / 1024:.2f} KB"
    file_size_kb.short_description = _('File Size')

    def has_add_permission(self, request):
        return False
