"""
URL configuration for Plateforme project.
"""
from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.utils.translation import gettext_lazy as _

# ============================================
# ADMIN SITE CUSTOMIZATION
# ============================================
admin.site.site_header = _('Arabic NLP Platform Administration')
admin.site.site_title = _('Arabic NLP Admin')
admin.site.index_title = _('Welcome to the Administration Dashboard')
urlpatterns += i18n_patterns(
    path('search/', include('search.urls', namespace='search')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('accounts/', include('allauth.urls')),
    path('projects/', include('projects.urls', namespace='projects')),
    path('forum/', include('forum.urls', namespace='forum')),
    path('events/', include('events.urls', namespace='events')),
    path('resources/', include('resources.urls', namespace='resources')),
    path('institutions/', include('institutions.urls', namespace='institutions')),
    path('QA/', include('QA.urls')),
    path('notifications/', include('notifications.urls', namespace='notifications')),
    path('chatbot/', include('chatbot.urls')),
    path('', include('pages.urls')),
    path('admin/', admin.site.urls),
    path('', include('translate.urls')),
)
# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)