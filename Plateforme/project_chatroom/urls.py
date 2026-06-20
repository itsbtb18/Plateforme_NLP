from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectChatViewSet, ProjectChatMessageViewSet

app_name = 'project_chatroom'

router = DefaultRouter()
router.register(r'chats', ProjectChatViewSet, basename='chat')
router.register(r'messages', ProjectChatMessageViewSet, basename='message')

urlpatterns = [
    path('', include(router.urls)),
]
