from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from .models import ChatSession, ChatMessage, ChatFeedback


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('display_session_id', 'user_email', 'pdf_status', 'is_active', 'message_count', 'created_at', 'updated_at')
    list_filter = ('is_active', 'pdf_uploaded', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'fastapi_session_id', 'pdf_filename')
    readonly_fields = ('id', 'fastapi_session_id', 'created_at', 'updated_at', 'display_messages')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('Session Info'), {
            'fields': ('id', 'fastapi_session_id', 'user', 'is_active')
        }),
        (_('PDF Context'), {
            'fields': ('pdf_uploaded', 'pdf_filename')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at')
        }),
        (_('Messages'), {
            'fields': ('display_messages',),
            'classes': ('collapse',)
        }),
    )
    
    def display_session_id(self, obj):
        return format_html('<code>{}</code>', obj.fastapi_session_id[:16] + '...')
    display_session_id.short_description = _('Session ID')
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = _('User')
    user_email.admin_order_field = 'user__email'
    
    def pdf_status(self, obj):
        if obj.pdf_uploaded:
            return format_html(
                '<span style="color: green;">✓ {}</span>',
                obj.pdf_filename or _('Uploaded')
            )
        return format_html('<span style="color: gray;">✗ {}</span>', _('No PDF'))
    pdf_status.short_description = _('PDF Status')
    
    def message_count(self, obj):
        count = obj.messages.count()
        return format_html(
            '<span style="padding: 2px 8px; background: #007bff; color: white; border-radius: 12px;">{}</span>',
            count
        )
    message_count.short_description = _('Messages')
    
    def display_messages(self, obj):
        messages = obj.messages.all()[:50]  # Limit to 50 most recent
        if not messages:
            return _('No messages yet')
        
        html = '<div style="max-height: 400px; overflow-y: auto;">'
        for msg in messages:
            color = {
                'user': '#007bff',
                'bot': '#28a745',
                'system': '#ffc107',
                'error': '#dc3545'
            }.get(msg.message_type, '#6c757d')
            
            html += f'''
            <div style="margin-bottom: 10px; padding: 8px; border-left: 3px solid {color}; background: #f8f9fa;">
                <strong style="color: {color};">{msg.get_message_type_display()}</strong>
                <small style="color: #6c757d; float: right;">{msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</small>
                <br>
                <span>{msg.content[:200]}{" ..." if len(msg.content) > 200 else ""}</span>
            </div>
            '''
        html += '</div>'
        return format_html(html)
    display_messages.short_description = _('Recent Messages')


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('display_id', 'session_display', 'message_type', 'content_preview', 'language', 'source', 'timestamp')
    list_filter = ('message_type', 'source', 'language', 'timestamp')
    search_fields = ('content', 'session__fastapi_session_id', 'session__user__email')
    readonly_fields = ('id', 'session', 'timestamp', 'display_content')
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        (_('Message Info'), {
            'fields': ('id', 'session', 'message_type', 'source', 'language')
        }),
        (_('Content'), {
            'fields': ('display_content',)
        }),
        (_('Timestamp'), {
            'fields': ('timestamp',)
        }),
    )
    
    def display_id(self, obj):
        return format_html('<code>{}</code>', str(obj.id)[:8] + '...')
    display_id.short_description = _('ID')
    
    def session_display(self, obj):
        return format_html(
            '<a href="/admin/chatbot/chatsession/{}/change/">{}</a>',
            obj.session.id,
            obj.session.fastapi_session_id[:12] + '...'
        )
    session_display.short_description = _('Session')
    
    def content_preview(self, obj):
        preview = obj.content[:80]
        if len(obj.content) > 80:
            preview += '...'
        return preview
    content_preview.short_description = _('Content')
    
    def display_content(self, obj):
        return format_html(
            '<div style="padding: 10px; background: #f8f9fa; border-radius: 4px; white-space: pre-wrap; font-family: monospace;">{}</div>',
            obj.content
        )
    display_content.short_description = _('Full Content')


@admin.register(ChatFeedback)
class ChatFeedbackAdmin(admin.ModelAdmin):
    list_display = ('display_id', 'user_email', 'rating_display', 'message_preview', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('user__email', 'comment', 'message__content')
    readonly_fields = ('id', 'message', 'user', 'created_at', 'display_message_content')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('Feedback Info'), {
            'fields': ('id', 'message', 'user', 'rating')
        }),
        (_('Comment'), {
            'fields': ('comment',)
        }),
        (_('Related Message'), {
            'fields': ('display_message_content',),
            'classes': ('collapse',)
        }),
        (_('Timestamp'), {
            'fields': ('created_at',)
        }),
    )
    
    def display_id(self, obj):
        return format_html('<code>{}</code>', str(obj.id)[:8] + '...')
    display_id.short_description = _('ID')
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = _('User')
    user_email.admin_order_field = 'user__email'
    
    def rating_display(self, obj):
        stars = '⭐' * obj.rating
        color = {
            1: '#dc3545',
            2: '#fd7e14',
            3: '#ffc107',
            4: '#20c997',
            5: '#28a745'
        }.get(obj.rating, '#6c757d')
        
        return format_html(
            '<span style="color: {}; font-size: 16px;">{} ({}/5)</span>',
            color, stars, obj.rating
        )
    rating_display.short_description = _('Rating')
    
    def message_preview(self, obj):
        content = obj.message.content[:60]
        if len(obj.message.content) > 60:
            content += '...'
        return content
    message_preview.short_description = _('Message')
    
    def display_message_content(self, obj):
        return format_html(
            '<div style="padding: 10px; background: #f8f9fa; border-radius: 4px; white-space: pre-wrap;">{}</div>',
            obj.message.content
        )
    display_message_content.short_description = _('Full Message Content')
