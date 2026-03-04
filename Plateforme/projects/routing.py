from django.urls import re_path

from .consumers import ProjectChatConsumer

websocket_urlpatterns = [
    re_path(r"^ws/projects/chat/(?P<project_id>[^/]+)/$", ProjectChatConsumer.as_asgi()),
]
