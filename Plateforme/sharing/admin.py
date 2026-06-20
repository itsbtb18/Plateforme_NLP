from django.contrib import admin
from .models import Share, ShareReply


class ShareReplyInline(admin.TabularInline):
    model = ShareReply
    extra = 0
    readonly_fields = ('author', 'content', 'created_at')


@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'content_title', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('sender__email', 'receiver__email', 'content_title')
    readonly_fields = ('id', 'sender', 'receiver', 'content_type', 'object_id',
                       'content_title', 'content_url', 'created_at', 'seen_at')
    inlines = [ShareReplyInline]


@admin.register(ShareReply)
class ShareReplyAdmin(admin.ModelAdmin):
    list_display = ('share', 'author', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('author__email', 'content')
    readonly_fields = ('id', 'share', 'author', 'created_at')
