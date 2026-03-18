from rest_framework import serializers
from django.contrib.auth import get_user_model
from accounts.serializers import UserSerializer
from .models import ProjectChat, ProjectChatMessage, ProjectChatFileAttachment

User = get_user_model()


class ProjectChatFileAttachmentSerializer(serializers.ModelSerializer):
    is_image = serializers.SerializerMethodField()
    file_extension = serializers.SerializerMethodField()

    class Meta:
        model = ProjectChatFileAttachment
        fields = ['id', 'file', 'attachment_type', 'original_filename', 'file_size', 'uploaded_by', 'uploaded_at', 'is_image', 'file_extension']
        read_only_fields = ['id', 'uploaded_at', 'is_image', 'file_extension']

    def get_is_image(self, obj):
        return obj.is_image()

    def get_file_extension(self, obj):
        return obj.get_file_extension()


class ProjectChatMessageSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    attachments = ProjectChatFileAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = ProjectChatMessage
        fields = ['id', 'chat', 'author', 'content', 'attachments', 'created_at', 'updated_at', 'is_edited']
        read_only_fields = ['id', 'chat', 'author', 'created_at', 'updated_at', 'is_edited']

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


class ProjectChatDetailSerializer(serializers.ModelSerializer):
    messages = ProjectChatMessageSerializer(many=True, read_only=True)
    project_title = serializers.CharField(source='project.title', read_only=True)
    can_user_access = serializers.SerializerMethodField()

    class Meta:
        model = ProjectChat
        fields = ['id', 'project', 'project_title', 'messages', 'created_at', 'updated_at', 'can_user_access']
        read_only_fields = ['id', 'project', 'created_at', 'updated_at']

    def get_can_user_access(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.can_user_access(request.user)
        return False


class ProjectChatListSerializer(serializers.ModelSerializer):
    project_title = serializers.CharField(source='project.title', read_only=True)
    last_message = serializers.SerializerMethodField()
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = ProjectChat
        fields = ['id', 'project', 'project_title', 'last_message', 'message_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'project', 'created_at', 'updated_at']

    def get_last_message(self, obj):
        last_message = obj.messages.last()
        if last_message:
            return ProjectChatMessageSerializer(last_message).data
        return None

    def get_message_count(self, obj):
        return obj.messages.count()


class ProjectChatMessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectChatMessage
        fields = ['content']

    def create(self, validated_data):
        chat_id = self.context['view'].kwargs['chat_id']
        validated_data['chat_id'] = chat_id
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)
