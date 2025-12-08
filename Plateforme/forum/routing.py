from django.urls import re_path
from .consumers import ChatroomConsumer

websocket_urlpatterns = [
    re_path(
        r"^ws/forum/chatroom/(?P<chatroom_id>[^/]+)/$",
        ChatroomConsumer.as_asgi(),  # type: ignore[arg-type]
    ),
]
