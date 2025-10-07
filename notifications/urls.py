from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('api/list/', views.api_notification_list, name='api_list'),
    path('api/mark-as-read/<uuid:notification_id>/', views.api_mark_as_read, name='api_mark_as_read'),
    path('api/mark-all-read/', views.api_mark_all_as_read, name='api_mark_all_as_read'),
    path('api/count/', views.api_notification_count, name='api_notification_count'),
    path('api/list/filtered/', views.api_notification_list_filtered, name='api_list_filtered'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('delete-all/', views.delete_all_notifications, name='delete_all'),
    path('mark-read/<uuid:notification_id>/', views.mark_read, name='mark_read'),
    path('ajax/count/', views.api_notification_count, name='ajax_count'),
]