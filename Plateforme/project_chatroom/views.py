from rest_framework import viewsets, status, permissions as drf_permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.db.models import Q
from .models import ProjectChat, ProjectChatMessage, ProjectChatFileAttachment
from .serializers import (
    ProjectChatDetailSerializer,
    ProjectChatListSerializer,
    ProjectChatMessageSerializer,
    ProjectChatMessageCreateSerializer,
)
from .permissions import IsProjectChatMember, CanAccessProjectChat


class ProjectChatViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving project chats.
    Only shows chats for projects where the user is a member.
    """
    serializer_class = ProjectChatListSerializer
    permission_classes = [drf_permissions.IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        """Return only chats for projects where user is an accepted member"""
        user = self.request.user
        # Get all projects where user is an accepted member
        from projects.models import ProjectMember
        user_projects = ProjectMember.objects.filter(
            member=user,
            status='accepted'
        ).values_list('project_id', flat=True)
        
        return ProjectChat.objects.filter(project_id__in=user_projects).select_related('project')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProjectChatDetailSerializer
        return ProjectChatListSerializer

    @action(detail=True, methods=['get'], permission_classes=[drf_permissions.IsAuthenticated])
    def messages(self, request, id=None):
        """Get all messages for a specific chat"""
        chat = self.get_object()
        
        # Check if user has access
        if not chat.can_user_access(request.user):
            return Response(
                {'detail': 'You do not have permission to access this chat.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        messages = chat.messages.all()
        serializer = ProjectChatMessageSerializer(messages, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[drf_permissions.IsAuthenticated])
    def send_message(self, request, id=None):
        """Send a message to the chat"""
        chat = self.get_object()
        
        # Check if user has access
        if not chat.can_user_access(request.user):
            return Response(
                {'detail': 'You do not have permission to access this chat.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ProjectChatMessageCreateSerializer(
            data=request.data,
            context={'request': request, 'view': self, 'chat_id': id}
        )
        
        if serializer.is_valid():
            message = serializer.save(chat=chat, author=request.user)
            return Response(
                ProjectChatMessageSerializer(message).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[drf_permissions.IsAuthenticated])
    def upload_file(self, request, id=None):
        """Upload a file or photo to a message"""
        chat = self.get_object()
        
        # Check if user has access
        if not chat.can_user_access(request.user):
            return Response(
                {'detail': 'You do not have permission to access this chat.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Required fields
        message_id = request.data.get('message_id')
        file = request.FILES.get('file')
        
        if not message_id or not file:
            return Response(
                {'detail': 'message_id and file are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the message
        message = get_object_or_404(ProjectChatMessage, id=message_id, chat=chat)
        
        # Only the author can add files to their message
        if message.author != request.user:
            return Response(
                {'detail': 'You can only add files to your own messages.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Determine attachment type
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}
        import os
        file_ext = os.path.splitext(file.name)[1].lower()
        attachment_type = 'image' if file_ext in image_extensions else 'file'
        
        # Create attachment
        attachment = ProjectChatFileAttachment.objects.create(
            message=message,
            file=file,
            attachment_type=attachment_type,
            original_filename=file.name,
            file_size=file.size,
            uploaded_by=request.user
        )
        
        from .serializers import ProjectChatFileAttachmentSerializer
        return Response(
            ProjectChatFileAttachmentSerializer(attachment).data,
            status=status.HTTP_201_CREATED
        )


class ProjectChatMessageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing project chat messages.
    Users can only view and edit their own messages.
    """
    serializer_class = ProjectChatMessageSerializer
    permission_classes = [drf_permissions.IsAuthenticated]
    lookup_field = 'id'
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        """Return messages from chats where user is a member"""
        user = self.request.user
        from projects.models import ProjectMember
        user_projects = ProjectMember.objects.filter(
            member=user,
            status='accepted'
        ).values_list('project_id', flat=True)
        
        return ProjectChatMessage.objects.filter(
            chat__project_id__in=user_projects
        ).select_related('author', 'chat')

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        """Only allow users to edit their own messages"""
        if serializer.instance.author != self.request.user:
            return Response(
                {'detail': 'You can only edit your own messages.'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer.save(is_edited=True)

    def perform_destroy(self, instance):
        """Only allow users to delete their own messages"""
        if instance.author != self.request.user and not self.request.user.is_staff:
            return Response(
                {'detail': 'You can only delete your own messages.'},
                status=status.HTTP_403_FORBIDDEN
            )
        instance.delete()
