"""
URL configuration for Plateforme project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from os import stat
from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from Plateforme import settings


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
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

