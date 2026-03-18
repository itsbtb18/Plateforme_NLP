from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import ProjectChat, ProjectChatMessage, ProjectChatFileAttachment
from .serializers import ProjectChatMessageSerializer
import json
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class ProjectChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time project chat messaging.
    """

    async def connect(self):
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.chat_group_name = f'project_chat_{self.chat_id}'
        self.user = self.scope['user']

        # Check if user has access to the chat
        has_access = await self.check_user_access()
        
        if not has_access:
            await self.close()
            return

        # Join the group
        await self.channel_layer.group_add(
            self.chat_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave the group
        await self.channel_layer.group_discard(
            self.chat_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'chat_message':
                await self.handle_chat_message(data)
            elif message_type == 'typing':
                await self.handle_typing_indicator(data)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {text_data}")
            await self.send_error('Invalid JSON format')

    async def handle_chat_message(self, data):
        """Handle incoming chat messages"""
        content = data.get('content', '').strip()
        
        if not content:
            await self.send_error('Message content cannot be empty')
            return

        # Save message to database
        message = await self.save_message(content)
        
        if message:
            # Broadcast to group
            await self.channel_layer.group_send(
                self.chat_group_name,
                {
                    'type': 'chat_message',
                    'message': message
                }
            )

    async def handle_typing_indicator(self, data):
        """Handle typing indicators"""
        is_typing = data.get('is_typing', False)
        
        await self.channel_layer.group_send(
            self.chat_group_name,
            {
                'type': 'typing_indicator',
                'user_id': str(self.user.id),
                'user_name': self.user.full_name,
                'is_typing': is_typing
            }
        )

    async def chat_message(self, event):
        """Receive message from group and send to WebSocket"""
        message = event['message']
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': message
        }))

    async def typing_indicator(self, event):
        """Receive typing indicator from group"""
        await self.send(text_data=json.dumps({
            'type': 'typing_indicator',
            'user_id': event['user_id'],
            'user_name': event['user_name'],
            'is_typing': event['is_typing']
        }))

    async def send_error(self, message):
        """Send error message to client"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))

    @database_sync_to_async
    def check_user_access(self):
        """Check if user is a member of the project"""
        try:
            chat = ProjectChat.objects.get(id=self.chat_id)
            return chat.can_user_access(self.user)
        except ProjectChat.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, content):
        """Save message to database and return serialized data"""
        try:
            chat = ProjectChat.objects.get(id=self.chat_id)
            message = ProjectChatMessage.objects.create(
                chat=chat,
                author=self.user,
                content=content
            )
            serializer = ProjectChatMessageSerializer(message)
            return serializer.data
        except ProjectChat.DoesNotExist:
            logger.error(f"Chat {self.chat_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            return None
