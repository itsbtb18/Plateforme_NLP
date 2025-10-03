import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Plateforme.settings')
django_asgi_app = get_asgi_application()

# Import websocket routes
to_imports = []
from notifications import routing as notifications_routing
from forum import routing as chatroom_routing

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                # Combine notification routes with chatroom routes
                notifications_routing.websocket_urlpatterns + 
                chatroom_routing.websocket_urlpatterns
            )
        )
    ),
})