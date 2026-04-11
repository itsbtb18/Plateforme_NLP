# consumers.py
import json
import logging
from typing import Any, cast

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.utils.html import escape

from .models import BannedUser, ChatRoom, Message

logger = logging.getLogger(__name__)


class ChatroomConsumer(WebsocketConsumer):
    room_group_name: str
    chatroom_id: str
    chatroom: ChatRoom | None = None
    user: Any | None = None

    def connect(self):
        user = cast(Any | None, self.scope.get("user"))
        if user is None or not getattr(user, "is_authenticated", False):
            self.close()
            return
        self.user = user

        url_route = cast(dict[str, Any], self.scope.get("url_route") or {})
        kwargs = cast(dict[str, Any], url_route.get("kwargs") or {})
        chatroom_id = kwargs.get("chatroom_id")
        if not chatroom_id:
            self.close()
            return
        self.chatroom_id = str(chatroom_id)
        try:
            self.chatroom = ChatRoom.objects.get(id=self.chatroom_id)
        except ChatRoom.DoesNotExist:
            self.close()
            return

        if BannedUser.objects.filter(chatroom=self.chatroom, user=self.user).exists():
            self.close()
            return

        self.room_group_name = f"chat_{self.chatroom_id}"
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name, self.channel_name
        )
        self.accept()

    def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            async_to_sync(self.channel_layer.group_discard)(
                self.room_group_name, self.channel_name
            )

    def receive(self, text_data):
        if self.chatroom is None or self.user is None:
            return
        try:
            text_data_json = json.loads(text_data)
            message_content = text_data_json.get("message", "").strip()
            parent_id = (text_data_json.get("parent_id") or "").strip()
            if not message_content:
                return
            if BannedUser.objects.filter(
                chatroom=self.chatroom, user=self.user
            ).exists():
                return

            parent_message = None
            if parent_id:
                parent_message = Message.objects.filter(
                    id=parent_id,
                    chatroom=self.chatroom,
                ).first()

            message = Message.objects.create(
                chatroom=self.chatroom,
                user=self.user,
                content=message_content,
                parent=parent_message,
            )
            # Get localized user name
            user_name = getattr(self.user, "get_full_name_display", str(self.user))
            if callable(user_name):
                user_name = user_name()
            else:
                user_name = str(user_name) if user_name else str(self.user)

            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message_id": str(message.id),
                    "content": escape(message.content),
                    "rendered_content": message.rendered_content,
                    "user_id": str(self.user.id),
                    "user_name": escape(user_name),
                    "timestamp": message.timestamp.strftime("%d/%m/%Y %H:%M"),
                    "is_edited": message.is_edited,
                    "profile_url": f"/accounts/profile/{self.user.id}/",
                    "parent_id": str(message.parent_id) if message.parent_id else None,
                },
            )
        except json.JSONDecodeError:
            pass
        except Exception:
            logger.exception("Error in ChatroomConsumer.receive")

    def chat_message(self, event):
        self.send(
            text_data=json.dumps(
                {
                    "message_id": event["message_id"],
                    "content": event["content"],
                    "rendered_content": event.get("rendered_content", ""),
                    "user_id": event["user_id"],
                    "user_name": event["user_name"],
                    "timestamp": event["timestamp"],
                    "is_current_user": bool(
                        self.user and str(self.user.id) == event["user_id"]
                    ),
                    "is_edited": event.get("is_edited", False),
                    "profile_url": event.get("profile_url", "#"),
                    "parent_id": event.get("parent_id"),
                }
            )
        )
