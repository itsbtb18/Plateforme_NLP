import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Notification

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_authenticated:
            self.group_name = f"user_{self.user.id}_notifications"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            await self.send_unread_notifications()
        else:
            await self.close()

    async def disconnect(self, close_code):
        if self.user.is_authenticated:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get('action') == 'mark_as_read':
            await self.mark_as_read(data.get('notification_id'))
        elif data.get('action') == 'mark_all_as_read':
            await self.mark_all_as_read()

    async def notification_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'notification': event['notification']
        }))

    async def send_unread_notifications(self):
        notifications = await self.get_unread_notifications()
        await self.send(text_data=json.dumps({
            'type': 'notification_list',
            'notifications': notifications
        }))

    @database_sync_to_async
    def get_unread_notifications(self):
        return [
            {
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'created_at': n.created_at.isoformat(),
                'read': n.read,
            }
            for n in Notification.objects.filter(recipient=self.user, read=False).order_by('-created_at')[:10]
        ]

    @database_sync_to_async
    def mark_as_read(self, notification_id):
        Notification.objects.filter(id=notification_id, recipient=self.user).update(read=True)

    @database_sync_to_async
    def mark_all_as_read(self):
        Notification.objects.filter(recipient=self.user, read=False).update(read=True)