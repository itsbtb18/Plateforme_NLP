import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Plateforme.settings")
django_asgi_app = get_asgi_application()

# Import websocket routes
from direct_messages import routing as direct_messages_routing
from forum import routing as chatroom_routing
from notifications import routing as notifications_routing
from projects import routing as projects_routing
from scraping import routing as scraping_routing

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(
                    # Combine notification routes with chatroom routes
                    notifications_routing.websocket_urlpatterns
                    + chatroom_routing.websocket_urlpatterns
                    + projects_routing.websocket_urlpatterns
                    + direct_messages_routing.websocket_urlpatterns
                    + scraping_routing.websocket_urlpatterns
                )
            )
        ),
    }
)
