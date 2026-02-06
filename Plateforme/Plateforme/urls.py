"""
URL configuration for Plateforme project.
"""
from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns


urlpatterns = [
    path('search/', include('search.urls', namespace='search')),  # MOVE THIS TO THE TOP
    path('i18n/', include('django.conf.urls.i18n')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('accounts/', include('allauth.urls')),
    path('projects/', include('projects.urls', namespace='projects')),
    path('forum/', include('forum.urls', namespace='forum')),
    path('events/', include('events.urls', namespace='events')),
    path('resources/', include('resources.urls', namespace='resources')),
    path('institutions/', include('institutions.urls', namespace='institutions')),
    path('QA/', include('QA.urls')),
    path('notifications/', include('notifications.urls', namespace='notifications')),
    path('admin/', admin.site.urls),
    path('chatbot/', include('chatbot.urls')),
    path('', include('pages.urls')),      # Keep empty paths at the bottom
    path('', include('translate.urls')),  # Keep empty paths at the bottom
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)