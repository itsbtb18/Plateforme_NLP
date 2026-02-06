# search/urls.py
from django.urls import path
from .views import GlobalSearchView, SearchAutocompleteView

app_name = 'search'

urlpatterns = [
    path('', GlobalSearchView.as_view(), name='global_search'),
    path('autocomplete/', SearchAutocompleteView.as_view(), name='autocomplete'),
]