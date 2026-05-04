from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('', views.EventListView.as_view(), name='event_list'),
    path('<uuid:pk>/', views.EventDetailView.as_view(), name='event_detail'),
<<<<<<< HEAD
    path('<uuid:pk>/convert-to-text/', views.event_convert_to_text, name='event-convert-to-text'),
=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    path('<uuid:pk>/export.ics/', views.event_ics_export, name='event_ics_export'),
    path('create/', views.EventCreateView.as_view(), name='event_create'),
    path('<uuid:pk>/update/', views.EventUpdateView.as_view(), name='event_update'),
    path('<uuid:pk>/delete/', views.EventDeleteView.as_view(), name='event_delete'),
    path('<uuid:pk>/register/', views.register_for_event, name='event_register'),
    path('<uuid:pk>/unregister/', views.unregister_from_event, name='event_unregister'),
    path('<uuid:pk>/validate/', views.event_validate, name='event_validate'),
]
