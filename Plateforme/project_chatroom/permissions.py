from rest_framework import permissions
from .models import ProjectChat
from projects.models import ProjectMember


class IsProjectChatMember(permissions.BasePermission):
    """
    Permission to check if the user is a member of the project
    associated with the chatroom.
    """

    def has_permission(self, request, view):
        # Allow any user to list chats (they'll only see their own)
        if request.method in permissions.SAFE_METHODS and hasattr(view, 'action') and view.action == 'list':
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Only allow access if user is a member of the project
        return obj.can_user_access(request.user)


class IsProjectMember(permissions.BasePermission):
    """
    Permission to check if the user is a member of a specific project
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        # obj is the message
        return obj.chat.can_user_access(request.user)


class CanAccessProjectChat(permissions.BasePermission):
    """
    Permission for accessing project chat messages and creating new messages.
    Ensures user is an accepted member of the project.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get the chat_id from URL kwargs
        chat_id = view.kwargs.get('chat_id')
        if not chat_id:
            return False
        
        try:
            chat = ProjectChat.objects.get(id=chat_id)
            return chat.can_user_access(request.user)
        except ProjectChat.DoesNotExist:
            return False
