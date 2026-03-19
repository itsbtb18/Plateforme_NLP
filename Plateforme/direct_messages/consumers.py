import json
from typing import Any, Dict, Optional, cast

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.utils.html import escape

from .models import Conversation


class DirectMessageConsumer(WebsocketConsumer):
    """
    Websocket for direct_messages thread updates.
    - Messages are persisted via HTTP POST in views.py.
    - This consumer mainly delivers server broadcasts to participants.
    """

    conversation_id: str
    room_group_name: str
    conversation: Optional[Conversation] = None
    user: Optional[Any] = None

    @staticmethod
    def _display_name(user: Any) -> str:
        raw = getattr(user, "get_full_name_display", "") or ""
        name = raw() if callable(raw) else raw
        name = (str(name) if name is not None else "").strip()
        if name:
            return name
        email = (getattr(user, "email", "") or "").strip()
        return email.split("@")[0] if email else "User"

    def connect(self):
        user = cast(Optional[Any], self.scope.get("user"))
        if user is None or not getattr(user, "is_authenticated", False):
            self.close()
            return
        self.user = user

        url_route = cast(Dict[str, Any], self.scope.get("url_route") or {})
        kwargs = cast(Dict[str, Any], url_route.get("kwargs") or {})
        conversation_id = kwargs.get("conversation_id")
        if not conversation_id:
            self.close()
            return
        self.conversation_id = str(conversation_id)

        try:
            self.conversation = Conversation.objects.get(id=self.conversation_id)
        except Conversation.DoesNotExist:
            self.close()
            return

        if not self.conversation.has_participant(self.user):
            self.close()
            return

        self.room_group_name = f"dm_{self.conversation_id}"
        async_to_sync(self.channel_layer.group_add)(self.room_group_name, self.channel_name)
        self.accept()

    def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            async_to_sync(self.channel_layer.group_discard)(self.room_group_name, self.channel_name)

    def receive(self, text_data: str):
        """
        Optional client -> server events (e.g. typing).
        We keep this minimal to avoid introducing new behaviors.
        """
        if self.user is None:
            return
        try:
            payload = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            return
        if payload.get("type") == "typing":
            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                {
                    "type": "dm_typing",
                    "user_id": str(self.user.id),
                    "user_name": escape(self._display_name(self.user)),
                },
            )

    def dm_message(self, event):
        if not self.user:
            return
        self.send(
            text_data=json.dumps(
                {
                    "event": "message",
                    "message": {
                        "id": event.get("id", ""),
                        "sender_id": event.get("sender_id", ""),
                        "sender_name": event.get("sender_name", ""),
                        "sender_avatar_url": event.get("sender_avatar_url", ""),
                        "message_type": event.get("message_type", "text"),
                        "content": event.get("content", ""),
                        "file_url": event.get("file_url", ""),
                        "created_at": event.get("created_at", ""),
                    },
                }
            )
        )

    def dm_typing(self, event):
        if self.user and str(self.user.id) == str(event.get("user_id", "")):
            return
        self.send(
            text_data=json.dumps(
                {
                    "event": "typing",
                    "user_id": event.get("user_id", ""),
                    "user_name": event.get("user_name", ""),
                }
            )
        )

