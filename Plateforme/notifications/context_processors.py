from .services import NotificationService
from .models import Notification

def notification_processor(request):
    """
    Context processor to make notifications available in all templates.
    Provides both recent notifications (read + unread) and unread count.
    """
    context = {
        'notifications': [],
        'unread_notifications_count': 0,
    }
    
    if request.user.is_authenticated:
        # Get the 10 most recent notifications (both read and unread) for dropdown
        notifications = Notification.objects.filter(
            recipient=request.user
        ).select_related('content_type').order_by('-created_at')[:10]
        
        # Count only unread
        unread_count = Notification.objects.filter(
            recipient=request.user, 
            read=False
        ).count()
        
        context['notifications'] = notifications
        context['unread_notifications_count'] = unread_count
    
    return context