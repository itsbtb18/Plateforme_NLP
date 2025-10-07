from django.urls import path
from .views import TopicListView, TopicCreateView, TopicUpdateView, TopicDeleteView, ChatRoomDetailView, ChatRoomCreateView, MessageDeleteView, ChatRoomListView, MessageUpdateView, BanUserView, UnbanUserView, TopicToggleStatusView, ChatRoomUpdateView, ChatRoomDeleteView
app_name = 'forum'

urlpatterns = [
    path('topics/', TopicListView.as_view(), name='topic-list'),
    path('topics/new/', TopicCreateView.as_view(), name='topic-new'),
    path('topics/<uuid:pk>/edit/', TopicUpdateView.as_view(), name='topic-update'),
    path('topics/<uuid:pk>/delete/', TopicDeleteView.as_view(), name='topic-delete'),
    path('topics/<uuid:pk>/toggle-status/', TopicToggleStatusView.as_view(), name='topic-toggle-status'),
    path('chatroom/<uuid:pk>/', ChatRoomDetailView.as_view(), name='chatroom-detail'),
    path('chatroom/<uuid:pk>/edit/', ChatRoomUpdateView.as_view(), name='chatroom-update'),
    path('chatroom/<uuid:pk>/delete/', ChatRoomDeleteView.as_view(), name='chatroom-delete'),
    path('topics/<uuid:topic_id>/chatroom/', ChatRoomListView.as_view(), name='chatroom-list'),
    path('topics/<uuid:topic_id>/chatroom/new/', ChatRoomCreateView.as_view(), name='chatroom-new'),  
    path('message/<uuid:pk>/delete/', MessageDeleteView.as_view(), name='message-delete'),
    path('message/<uuid:pk>/update/', MessageUpdateView.as_view(), name='message-update'),
    path('chatroom/<uuid:chatroom_pk>/ban/<uuid:user_pk>/', BanUserView.as_view(), name='ban-user'),
    path('chatroom/unban/<uuid:pk>/', UnbanUserView.as_view(), name='unban-user'),
]