from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from .models import Notification
from .services import NotificationService
from django.core.paginator import Paginator
from django.contrib import messages
from datetime import timedelta
from collections import OrderedDict


def group_notifications_by_date(notifications):
    """
    Group notifications by Today, Yesterday, and Earlier.
    Returns an OrderedDict with date groups.
    """
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    
    grouped = OrderedDict([
        ('today', []),
        ('yesterday', []),
        ('earlier', []),
    ])
    
    for notification in notifications:
        notification_date = notification.created_at.date()
        if notification_date == today:
            grouped['today'].append(notification)
        elif notification_date == yesterday:
            grouped['yesterday'].append(notification)
        else:
            grouped['earlier'].append(notification)
    
    return grouped


@login_required
def notification_list(request):
    
    """Vue pour afficher la liste des notifications"""
    base_queryset = Notification.objects.filter(recipient=request.user)
    notifications = base_queryset.order_by('-created_at')

    paginator = Paginator(notifications, 10)
    page = request.GET.get('page')
    notifications = paginator.get_page(page)
    
    action_required_types = {
        'PROJECT_INVITE',
        'PROJECT_INVITATION',
        'PROJECT_JOIN_REQUEST',
        'MEMBERSHIP_REQUEST',
        'LEAVE_REQUEST',
    }
    project_invite_types = {'PROJECT_INVITE', 'PROJECT_INVITATION'}
    join_request_types = {'PROJECT_JOIN_REQUEST', 'MEMBERSHIP_REQUEST'}

    notification_list = (
        notifications.object_list
        if hasattr(notifications, 'object_list')
        else notifications
    )
    for notification in notification_list:
        notification.requires_action = (
            notification.type in action_required_types and not notification.response_given
        )
        notification.is_project_invite = bool(
            notification.project_id and notification.type in project_invite_types
        )
        notification.is_join_request = bool(
            notification.project_id
            and notification.sender_id
            and notification.type in join_request_types
        )
        notification.is_leave_request = bool(
            notification.project_id
            and notification.sender_id
            and notification.type == 'LEAVE_REQUEST'
        )
    
    # Group notifications by date (Today, Yesterday, Earlier)
    grouped_notifications = group_notifications_by_date(notification_list)
    
    return render(request, 'notifications/list.html', {
        'notifications': notifications,
        'grouped_notifications': grouped_notifications,
        'user': request.user,  # Assurez-vous que l'utilisateur est explicitement passAc
        'total_notifications': base_queryset.count(),
        'unread_notifications': base_queryset.filter(read=False).count(),
        'action_required_count': base_queryset.filter(
            type__in=action_required_types,
            response_given=False
        ).count(),
    })


@login_required
def api_notification_list(request):
    """API to get recent notifications with full details for dropdown."""
    notifications = Notification.objects.filter(
        recipient=request.user
    ).select_related('content_type').order_by('-created_at')[:15]
    
    data = []
    for n in notifications:
        # Determine redirect URL
        redirect_url = reverse('notifications:go_to_notification', kwargs={'notification_id': n.id})
        
        # Get notification type icon
        type_icons = {
            'PROJECT_INVITATION': 'fa-user-plus',
            'MEMBERSHIP_REQUEST': 'fa-user-clock',
            'PROJECT_UPDATE': 'fa-flask',
            'TASK_ASSIGNED': 'fa-tasks',
            'LEAVE_REQUEST': 'fa-door-open',
            'COMMENT': 'fa-comment',
            'MESSAGE': 'fa-envelope',
            'EVENT_CREATED': 'fa-calendar-plus',
            'EVENT_APPROVED': 'fa-calendar-check',
            'RESOURCE_ADDED': 'fa-file-alt',
            'TOOL_ADDED': 'fa-tools',
            'CORPUS_UPDATE': 'fa-database',
            'RESEARCH_UPDATE': 'fa-microscope',
            'FORUM_TOPIC': 'fa-comments',
            'QA_ANSWER': 'fa-reply',
            'QA_COMMENT': 'fa-comment-dots',
            'POST_APPROVED': 'fa-check-circle',
            'INSTITUTION_UPDATE': 'fa-university',
            'SYSTEM': 'fa-cog',
        }
        
        # Get type color
        type_colors = {
            'PROJECT_INVITATION': 'bg-purple-100 text-purple-600',
            'MEMBERSHIP_REQUEST': 'bg-indigo-100 text-indigo-600',
            'PROJECT_UPDATE': 'bg-blue-100 text-blue-600',
            'TASK_ASSIGNED': 'bg-orange-100 text-orange-600',
            'COMMENT': 'bg-green-100 text-green-600',
            'EVENT_CREATED': 'bg-pink-100 text-pink-600',
            'EVENT_APPROVED': 'bg-emerald-100 text-emerald-600',
            'RESOURCE_ADDED': 'bg-cyan-100 text-cyan-600',
            'TOOL_ADDED': 'bg-amber-100 text-amber-600',
            'FORUM_TOPIC': 'bg-violet-100 text-violet-600',
            'QA_ANSWER': 'bg-teal-100 text-teal-600',
            'POST_APPROVED': 'bg-green-100 text-green-600',
        }
        
        data.append({
            'id': str(n.id),
            'title': n.get_localized_title(),
            'message': n.get_localized_message()[:100] + '...' if len(n.get_localized_message()) > 100 else n.get_localized_message(),
            'type': n.type,
            'type_display': str(n.get_type_display()),
            'icon': type_icons.get(n.type, 'fa-bell'),
            'color_class': type_colors.get(n.type, 'bg-gray-100 text-gray-600'),
            'created_at': n.created_at.isoformat(),
            'time_since': _time_since(n.created_at),
            'read': n.read,
            'url': redirect_url,
            'requires_action': n.type in {'PROJECT_INVITATION', 'MEMBERSHIP_REQUEST', 'LEAVE_REQUEST'} and not n.response_given,
        })
    
    unread_count = Notification.objects.filter(recipient=request.user, read=False).count()
    
    return JsonResponse({
        'notifications': data,
        'unread_count': unread_count,
    })


def _time_since(dt):
    """Helper to format time since in a friendly way."""
    now = timezone.now()
    diff = now - dt
    
    if diff.days > 7:
        return dt.strftime('%b %d')
    elif diff.days > 0:
        return f"{diff.days}d"
    elif diff.seconds >= 3600:
        return f"{diff.seconds // 3600}h"
    elif diff.seconds >= 60:
        return f"{diff.seconds // 60}m"
    else:
        return str(_("Just now"))


@login_required
def api_mark_as_read(request, notification_id):
    """API to mark a single notification as read."""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.read = True
    notification.read_at = timezone.now()
    notification.save(update_fields=['read', 'read_at'])
    
    unread_count = Notification.objects.filter(recipient=request.user, read=False).count()
    return JsonResponse({'success': True, 'unread_count': unread_count})


@login_required
def api_mark_all_as_read(request):
    """API to mark all notifications as read."""
    updated = Notification.objects.filter(recipient=request.user, read=False).update(
        read=True,
        read_at=timezone.now()
    )
    
    return JsonResponse({'success': True, 'updated_count': updated, 'unread_count': 0})

@login_required
def api_notification_count(request):
    """API pour obtenir le nombre de notifications non lues"""
    count = Notification.objects.filter(recipient=request.user, read=False).count()
    return JsonResponse({'count': count})

@login_required
def api_notification_list_filtered(request):
    """API pour obtenir une liste filtrÃ©e de notifications"""
    # ParamÃ¨tres de filtrage
    read = request.GET.get('read')
    if read is not None:
        read = read.lower() == 'true'
    
    limit = request.GET.get('limit')
    if limit:
        try:
            limit = int(limit)
        except ValueError:
            limit = None
    
    # RÃ©cupÃ©rer les notifications
    notifications = NotificationService.get_user_notifications(
        request.user, read=read, limit=limit
    )
    
    # Formater les donnÃ©es
    data = [{
        'id': n.id,
        'type': n.get_type_display(),
        'type_code': n.type,
        'title': n.get_localized_title(),
        'message': n.get_localized_message(),
        'created_at': n.created_at.isoformat(),
        'read': n.read,
        'read_at': n.read_at.isoformat() if n.read_at else None,
    } for n in notifications]
    
    return JsonResponse({'notifications': data})

@login_required
def mark_all_read(request):
    """Marks all unread notifications for the current user as read."""
    updated = request.user.notifications.filter(read=False).update(
        read=True,
        read_at=timezone.now()
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': str(_("All notifications marked as read.")),
            'updated_count': updated
        })
    
    messages.success(request, _("All notifications have been marked as read."))
    
    # Return to previous page or notifications list
    next_url = request.GET.get('next', request.META.get('HTTP_REFERER'))
    if next_url:
        return redirect(next_url)
    return redirect('notifications:list')


@login_required
def go_to_notification(request, notification_id):
    """
    Marks a notification as read and redirects to the associated content.
    This is the main entry point for clicking on notifications.
    """
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    
    # Mark as read
    if not notification.read:
        notification.read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=['read', 'read_at'])
    
    # Determine redirect URL based on notification type and content
    redirect_url = None
    
    # 1. Try content_object with get_absolute_url
    if notification.content_object:
        try:
            redirect_url = notification.content_object.get_absolute_url()
        except (AttributeError, Exception):
            pass
    
    # 2. Try project_id
    if not redirect_url and notification.project_id:
        try:
            redirect_url = reverse('projects:project_detail', kwargs={'project_id': notification.project_id})
        except Exception:
            pass
    
    # 3. Type-specific redirects
    if not redirect_url:
        type_redirects = {
            'EVENT_CREATED': 'events:event_list',
            'EVENT_APPROVED': 'events:event_list',
            'FORUM_TOPIC': 'forum:topic-list',
            'QA_ANSWER': 'QA:feed',
            'QA_COMMENT': 'QA:feed',
            'POST_APPROVED': 'QA:feed',
            'RESOURCE_ADDED': 'resources:list',
            'TOOL_ADDED': 'resources:tool_list',
            'CORPUS_UPDATE': 'resources:corpus_list',
            'INSTITUTION_UPDATE': 'institutions:institution_list',
        }
        
        if notification.type in type_redirects:
            try:
                redirect_url = reverse(type_redirects[notification.type])
            except Exception:
                pass
    
    # 4. Default fallback to notifications list
    if not redirect_url:
        redirect_url = reverse('notifications:list')
    
    return redirect(redirect_url)


@login_required
def mark_read(request, notification_id):
    """Marks a specific notification as read and redirects to associated content."""
    # Delegate to go_to_notification for consistent behavior
    return go_to_notification(request, notification_id)

def delete_all_notifications(request):
    Notification.objects.filter(recipient=request.user).delete()
    messages.success(request, _("All your notifications have been deleted."))
    return redirect('notifications:list') 


@login_required
def delete_notification(request, notification_id):
    """Delete a single notification."""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.delete()
    messages.success(request, _("Notification deleted successfully."))
    
    # Return to the referring page or notifications list
    next_url = request.GET.get('next', request.META.get('HTTP_REFERER'))
    if next_url:
        return redirect(next_url)
    return redirect('notifications:list')


@login_required
def api_delete_notification(request, notification_id):
    """API endpoint to delete a single notification."""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.delete()
    return JsonResponse({'success': True, 'message': str(_("Notification deleted successfully."))}) 



