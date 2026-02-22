from django.urls import path
from . import views

app_name = 'sharing'

urlpatterns = [
    # Modal helpers
    path('users/search/', views.user_search, name='user_search'),
    path('create/', views.create_share, name='create_share'),

    # Inbox / Sent
    path('inbox/', views.inbox, name='inbox'),
    path('sent/', views.sent, name='sent'),

    # Thread detail + reply
    path('thread/<uuid:share_id>/', views.share_detail, name='share_detail'),
    path('thread/<uuid:share_id>/reply/', views.add_reply, name='add_reply'),

    # Badge count (navbar)
    path('unread-count/', views.unread_count, name='unread_count'),
]
