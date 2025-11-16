"""
URL configuration for Plateforme project.
"""
from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from django.conf import settings


urlpatterns = [
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('accounts/', include('allauth.urls')),
    path('', include('pages.urls')),
    path('projects/', include('projects.urls', namespace='projects')),
    path('forum/', include('forum.urls', namespace='forum')),
    path('events/', include('events.urls', namespace='events')),
    path('resources/', include('resources.urls', namespace='resources')),
    path('institutions/', include('institutions.urls', namespace='institutions')),
    path('QA/', include('QA.urls')),
    path('notifications/', include('notifications.urls', namespace='notifications')),
    path('search/', include('search.urls', namespace='search')),
    path('admin/', admin.site.urls),
    path('chatbot/', include('chatbot.urls')),
    path('', include('translate.urls')),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Only serve media files locally if NOT using Cloudinary
    if settings.DEFAULT_FILE_STORAGE != 'cloudinary_storage.storage.MediaCloudinaryStorage':
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # When using Cloudinary, media files are served directly from Cloudinary's CDN
    # No local URL pattern needed - the avatar.url will return a Cloudinary URL