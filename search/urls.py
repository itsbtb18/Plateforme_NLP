# search/urls.py
from django.urls import path
from .views import GlobalSearchView
app_name = 'search'
urlpatterns = [
    path('', GlobalSearchView.as_view(), name='global_search'),
]