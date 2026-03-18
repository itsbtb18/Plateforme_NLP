from rest_framework import serializers
from django.contrib.auth import get_user_model
from institutions.models import Institution

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for CustomUser model.
    Provides basic user information for API responses.
    """
    institution_name = serializers.CharField(source='institution.name', read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'full_name_ar',
            'full_name_en',
            'bio',
            'bio_ar',
            'bio_en',
            'avatar',
            'speciality',
            'institution',
            'institution_name',
            'is_active',
            'status',
            'date_joined',
        ]
        read_only_fields = [
            'id',
            'date_joined',
            'status',
            'is_active',
        ]


class SimpleUserSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for user information.
    Used when only basic user details are needed.
    """
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'avatar',
        ]
        read_only_fields = fields
