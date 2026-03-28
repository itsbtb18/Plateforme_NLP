"""
URL configuration for Plateforme project.
"""

import logging

from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
from django.views.static import serve
from django.urls import re_path

logger = logging.getLogger(__name__)

# ============================================
# HEALTH CHECK (lightweight, no DB/template)
# ============================================
def health_check(request):
    return JsonResponse({"status": "ok"})


# ============================================
# ADMIN SITE CUSTOMIZATION
# ============================================
admin.site.site_header = _("Arabic NLP Platform Administration")
admin.site.site_title = _("Arabic NLP Admin")
admin.site.index_title = _("Welcome to the Administration Dashboard")

# URLs without language prefix
urlpatterns = [
    path("healthz/", health_check, name="health_check"),
    path("i18n/", include("django.conf.urls.i18n")),
]

# URLs with language prefix
localized_patterns = [
    path("search/", include("search.urls", namespace="search")),
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("accounts/", include("allauth.urls")),
    path("projects/", include("projects.urls", namespace="projects")),
    path("forum/", include("forum.urls", namespace="forum")),
    path("events/", include("events.urls", namespace="events")),
    path("resources/", include("resources.urls", namespace="resources")),
    path("institutions/", include("institutions.urls", namespace="institutions")),
    path("QA/", include("QA.urls")),
    path("notifications/", include("notifications.urls", namespace="notifications")),
    path("chatbot/", include("chatbot.urls")),
    path("messages/", include("direct_messages.urls", namespace="direct_messages")),
    path("sharing/", include("sharing.urls", namespace="sharing")),
    path("", include("pages.urls")),
    path("", include("translate.urls")),
    path("admin/", admin.site.urls),
]

try:
    localized_patterns.insert(
        -3, path("scraping/", include("scraping.urls", namespace="scraping"))
    )
except Exception as exc:
    logger.warning("scraping URLs disabled at startup: %s", exc)

urlpatterns += i18n_patterns(*localized_patterns)


# Serve static and media files for direct Django access (e.g. :8888)
# Nginx still serves these in the reverse-proxy path.
urlpatterns += [
    re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT}),
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]
