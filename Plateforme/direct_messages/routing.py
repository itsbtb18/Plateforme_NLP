from django.urls import re_path

from .consumers import DirectMessageConsumer

websocket_urlpatterns = [
    re_path(r"^ws/direct-messages/(?P<conversation_id>[^/]+)/$", DirectMessageConsumer.as_asgi()),
]

