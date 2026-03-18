"""
Views for settings management
Provides API endpoints and utility views for working with settings
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.admin.views.decorators import staff_member_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from .models import GlobalSettings
from .utils import get_global_settings
from .serializers import GlobalSettingsSerializer


@require_http_methods(["GET"])
def settings_health_check(request):
    """
    Check if settings are properly configured
    Returns JSON with status of each setting category
    """
    try:
        settings = get_global_settings()
        
        status_check = {
            'platform': bool(settings.site_name),
            'email': bool(settings.email_from_address and settings.smtp_host),
            'notifications': settings.enable_email_notifications,
            'maintenance_mode': settings.maintenance_mode,
        }
        
        return JsonResponse({
            'status': 'ok',
            'checks': status_check,
            'maintenance_mode': settings.maintenance_mode,
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_settings_api(request):
    """
    API endpoint to get current global settings
    Requires admin authentication
    """
    settings = get_global_settings()
    serializer = GlobalSettingsSerializer(settings)
    return Response(serializer.data)


@staff_member_required
def settings_dashboard(request):
    """
    Dashboard view showing a summary of global settings
    Only accessible to staff members
    """
    settings = get_global_settings()
    
    context = {
        'settings': settings,
        'enabled_features': [
            attr for attr in dir(settings)
            if attr.startswith('enable_') and getattr(settings, attr)
        ],
        'email_configured': bool(settings.email_from_address and settings.smtp_host),
    }
    
    return render(request, 'settings/dashboard.html', context)
