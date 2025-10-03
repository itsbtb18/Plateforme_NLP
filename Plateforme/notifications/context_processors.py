from .services import NotificationService

def notification_processor(request):
    """
    Contexte processor pour rendre les notifications disponibles dans tous les templates
    """
    context = {
        'unread_notifications': [],
        'unread_notifications_count': 0
    }
    
    if request.user.is_authenticated:
        # Récupérer les 5 dernières notifications non lues
        notifications = NotificationService.get_user_notifications(
            request.user, read=False, limit=5
        )
        
        context['unread_notifications'] = notifications
        context['unread_notifications_count'] = notifications.count()
    
    return context