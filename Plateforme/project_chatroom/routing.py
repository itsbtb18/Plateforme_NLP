from django.urls import re_path
from .consumers import ProjectChatConsumer

websocket_urlpatterns = [
    re_path(r'ws/project-chat/(?P<chat_id>[\w-]+)/$', ProjectChatConsumer.as_asgi()),
]
