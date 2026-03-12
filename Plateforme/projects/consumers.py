import json
from typing import Any, Dict, Optional, cast

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.utils.html import escape

from .models import Project, ProjectChatMessage, ProjectChatRoom, ProjectMember


class ProjectChatConsumer(WebsocketConsumer):
    room_group_name: str
    project_id: str
    project: Optional[Project] = None
    room: Optional[ProjectChatRoom] = None
    user: Optional[Any] = None

    def _is_member(self, user, project: Project) -> bool:
        if user == project.coordinator:
            return True
        return ProjectMember.objects.filter(project=project, member=user, status="accepted").exists()

    def connect(self):
        user = cast(Optional[Any], self.scope.get("user"))
        if user is None or not getattr(user, "is_authenticated", False):
            self.close()
            return
        self.user = user

        url_route = cast(Dict[str, Any], self.scope.get("url_route") or {})
        kwargs = cast(Dict[str, Any], url_route.get("kwargs") or {})
        project_id = kwargs.get("project_id")
        if not project_id:
            self.close()
            return
        self.project_id = str(project_id)
        try:
            self.project = Project.objects.get(id=self.project_id)
        except Project.DoesNotExist:
            self.close()
            return

        if not self._is_member(self.user, self.project):
            self.close()
            return

        self.room, _ = ProjectChatRoom.objects.get_or_create(project=self.project)
        self.room_group_name = f"project_chat_{self.project_id}"
        async_to_sync(self.channel_layer.group_add)(self.room_group_name, self.channel_name)
        self.accept()

    def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            async_to_sync(self.channel_layer.group_discard)(self.room_group_name, self.channel_name)

    def receive(self, text_data):
        if self.room is None or self.user is None:
            return
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        event_type = payload.get("type")
        if event_type == "typing":
            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                {
                    "type": "chat_typing",
                    "user_id": str(self.user.id),
                    "user_name": escape(self.user.get_full_name_display),
                },
            )
            return

        message_content = (payload.get("message") or "").strip()
        if not message_content:
            return
        msg = ProjectChatMessage.objects.create(
            room=self.room,
            sender=self.user,
            content=message_content,
            message_type=ProjectChatMessage.MessageType.LINK
            if "http://" in message_content or "https://" in message_content
            else ProjectChatMessage.MessageType.TEXT,
        )
        msg.seen_by.add(self.user)
        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            {
                "type": "chat_message",
                "message_id": str(msg.id),
                "sender_id": str(self.user.id),
                "sender_name": escape(self.user.get_full_name_display),
                "content": escape(msg.content),
                "message_type": msg.message_type,
                "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M"),
            },
        )

    def chat_message(self, event):
        self.send(
            text_data=json.dumps(
                {
                    "event": "message",
                    "message_id": event["message_id"],
                    "sender_id": event["sender_id"],
                    "sender_name": event["sender_name"],
                    "content": event["content"],
                    "message_type": event["message_type"],
                    "created_at": event["created_at"],
                    "is_current_user": bool(self.user and str(self.user.id) == event["sender_id"]),
                }
            )
        )

    def chat_typing(self, event):
        if self.user and str(self.user.id) == event["user_id"]:
            return
        self.send(
            text_data=json.dumps(
                {
                    "event": "typing",
                    "user_id": event["user_id"],
                    "user_name": event["user_name"],
                }
            )
        )
