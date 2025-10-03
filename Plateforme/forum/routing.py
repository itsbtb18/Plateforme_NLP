from django.urls import path
from .consumers import ChatroomConsumer

websocket_urlpatterns = [
    path("ws/forum/chatroom/<str:chatroom_id>/", ChatroomConsumer.as_asgi()),
]