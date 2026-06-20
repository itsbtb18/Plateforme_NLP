from django.contrib import admin

from .models import Conversation, ConversationParticipant, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation_type",
        "status",
        "is_accepted",
        "user1",
        "user2",
        "group_name",
        "created_at",
    )
    list_filter = ("conversation_type", "status", "is_accepted", "created_at")
    search_fields = ("user1__email", "user2__email", "group_name")
    ordering = ("-created_at",)


@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "user", "is_admin", "joined_at")
    list_filter = ("is_admin", "joined_at")
    search_fields = ("conversation__group_name", "user__email")
    ordering = ("-joined_at",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "message_type", "is_read", "created_at")
    list_filter = ("message_type", "is_read", "created_at")
    search_fields = ("content", "sender__email")
    ordering = ("-created_at",)
