from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from .models import Notification
from .services import NotificationService
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages

@login_required
def notification_list(request):
    
    """Vue pour afficher la liste des notifications"""
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')

    paginator = Paginator(notifications, 10)  
    page = request.GET.get('page')
    try:
        notifications = paginator.page(page)
    except PageNotAnInteger:
        notifications = paginator.page(1)
    except EmptyPage:
        notifications = paginator.page(paginator.num_pages)
    
    
    
    return render(request, 'notifications/list.html', {
        'notifications': notifications,
        'user': request.user,  # Assurez-vous que l'utilisateur est explicitement passé
    })
@login_required
def api_notification_list(request):
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')[:20]
    data = [{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'created_at': n.created_at.isoformat(),
        'read': n.read,
    } for n in notifications]
    return JsonResponse({'notifications': data})

@login_required
def api_mark_as_read(request, notification_id):
    """API pour marquer une notification comme lue"""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.read = True
    notification.read_at = timezone.now()
    notification.save()
    
    return JsonResponse({'success': True})

@login_required
def api_mark_all_as_read(request):
    """API pour marquer toutes les notifications comme lues"""
    Notification.objects.filter(recipient=request.user, read=False).update(
        read=True,
        read_at=timezone.now()
    )
    
    return JsonResponse({'success': True})

@login_required
def api_notification_count(request):
    """API pour obtenir le nombre de notifications non lues"""
    count = Notification.objects.filter(recipient=request.user, read=False).count()
    return JsonResponse({'count': count})

@login_required
def api_notification_list_filtered(request):
    """API pour obtenir une liste filtrée de notifications"""
    # Paramètres de filtrage
    read = request.GET.get('read')
    if read is not None:
        read = read.lower() == 'true'
    
    limit = request.GET.get('limit')
    if limit:
        try:
            limit = int(limit)
        except ValueError:
            limit = None
    
    # Récupérer les notifications
    notifications = NotificationService.get_user_notifications(
        request.user, read=read, limit=limit
    )
    
    # Formater les données
    data = [{
        'id': n.id,
        'type': n.get_type_display(),
        'type_code': n.type,
        'title': n.title,
        'message': n.message,
        'created_at': n.created_at.isoformat(),
        'read': n.read,
        'read_at': n.read_at.isoformat() if n.read_at else None,
    } for n in notifications]
    
    return JsonResponse({'notifications': data})

@login_required
def mark_all_read(request):
    """Marque toutes les notifications non lues de l'utilisateur comme lues."""
    request.user.notifications.filter(read=False).update(read=True)
    messages.success(request, "All notifications have been marked as read.")
    return redirect('notifications:list')

@login_required
def mark_read(request, notification_id):
    """Marque une notification spécifique comme lue et redirige vers la liste."""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.read = True
    notification.read_at = timezone.now()
    notification.save()
    messages.success(request, "Notification marked as read.")
    # Rediriger vers la page d'où la requête provenait, ou par défaut la liste
    next_url = request.GET.get('next', request.META.get('HTTP_REFERER', redirect('notifications:list').url))
    return redirect(next_url)

def delete_all_notifications(request):
    Notification.objects.filter(recipient=request.user).delete()
    messages.success(request, "All your notifications have been deleted.")
    return redirect('notifications:list') 

