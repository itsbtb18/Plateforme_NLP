# consumers.py
from channels.generic.websocket import WebsocketConsumer
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from asgiref.sync import async_to_sync
import json
from .models import ChatRoom, Message, BannedUser

class ChatroomConsumer(WebsocketConsumer):
    def connect(self):
        self.user = self.scope['user']
        
        # Vérifier si l'utilisateur est authentifié
        if not self.user.is_authenticated:
            self.close()
            return
            
        self.chatroom_id = self.scope['url_route']['kwargs']['chatroom_id']
        
        try:
            self.chatroom = get_object_or_404(ChatRoom, id=self.chatroom_id)
        except:
            self.close()
            return
        
        # Vérifier si l'utilisateur est banni
        if BannedUser.objects.filter(chatroom=self.chatroom, user=self.user).exists():
            self.close()
            return
        
        # Use the chatroom ID as the channel group name
        self.room_group_name = f'chat_{self.chatroom_id}'
        
        # Join the channel group
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name, 
            self.channel_name
        )
        
        self.accept()
    
    def disconnect(self, close_code):
        # Leave the channel group
        if hasattr(self, 'room_group_name'):
            async_to_sync(self.channel_layer.group_discard)(
                self.room_group_name, 
                self.channel_name
            )
    
    def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_content = text_data_json.get('message', '').strip()
            
            # Vérifier que le message n'est pas vide
            if not message_content:
                return
            
            # Vérifier à nouveau si l'utilisateur est banni (sécurité)
            if BannedUser.objects.filter(chatroom=self.chatroom, user=self.user).exists():
                return
            
            # Create a new message in the database
            message = Message.objects.create(
                chatroom=self.chatroom,
                user=self.user,
                content=message_content
            )
            
            # Send the message to the channel group
            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message_id': str(message.id),
                    'content': message.content,
                    'user_id': str(self.user.id),
                    'user_name': str(self.user),
                    'timestamp': message.timestamp.strftime('%d/%m/%Y %H:%M'),
                    'is_edited': message.is_edited,
                    'profile_url': f'/accounts/profile/{self.user.id}/'  # Ajout de l'URL du profil
                }
            )
            
        except json.JSONDecodeError:
            # Ignorer les messages mal formatés
            pass
        except Exception as e:
            # Log l'erreur en production
            print(f"Erreur dans ChatroomConsumer.receive: {e}")
    
    def chat_message(self, event):
        # Send the message to the WebSocket
        self.send(text_data=json.dumps({
            'message_id': event['message_id'],
            'content': event['content'],
            'user_id': event['user_id'],
            'user_name': event['user_name'],
            'timestamp': event['timestamp'],
            'is_current_user': str(self.user.id) == event['user_id'],
            'is_edited': event.get('is_edited', False),
            'profile_url': event.get('profile_url', '#')
        }))