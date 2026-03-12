"""
Core application views.
Centralized views for platform-wide functionality.
"""
import logging
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.translation import gettext as _
from django.db.models import Q, Count, CharField
from django.db.models.functions import Concat
from django.db.models import Value
from typing import List, Dict, Any
from django.http import JsonResponse

logger = logging.getLogger(__name__)


@staff_member_required
def pending_content_dashboard(request):
    """
    Centralized dashboard showing all pending content across all models.
    Staff-only view for efficient content moderation.
    """
    from resources.models import Corpus, NLPTool, Course, Document
    from projects.models import Project
    from forum.models import Topic
    from events.models import Event
    
    # Aggregate all pending content
    pending_items = []
    
    # 1. Resources - Corpus
    for corpus in Corpus.objects.filter(approval_status='pending').select_related('author'):
        pending_items.append({
            'id': corpus.id,
            'type': 'Corpus',
            'type_class': 'corpus',
            'title': corpus.get_localized_title(),
            'author': corpus.author.get_full_name() if corpus.author else 'Unknown',
            'author_id': corpus.author.id if corpus.author else None,
            'created_at': corpus.created_at,
            'app_label': 'resources',
            'model_name': 'corpus',
            'admin_url': f'/admin/resources/corpus/{corpus.id}/change/',
            'detail_url': corpus.get_absolute_url() if hasattr(corpus, 'get_absolute_url') else None,
        })
    
    # 2. Resources - NLP Tools
    for tool in NLPTool.objects.filter(approval_status='pending').select_related('author'):
        pending_items.append({
            'id': tool.id,
            'type': 'NLP Tool',
            'type_class': 'nlptool',
            'title': tool.get_localized_title(),
            'author': tool.author.get_full_name() if tool.author else 'Unknown',
            'author_id': tool.author.id if tool.author else None,
            'created_at': tool.created_at,
            'app_label': 'resources',
            'model_name': 'nlptool',
            'admin_url': f'/admin/resources/nlptool/{tool.id}/change/',
            'detail_url': tool.get_absolute_url() if hasattr(tool, 'get_absolute_url') else None,
        })
    
    # 3. Resources - Courses
    for course in Course.objects.filter(approval_status='pending').select_related('author', 'institution'):
        pending_items.append({
            'id': course.id,
            'type': 'Course',
            'type_class': 'course',
            'title': course.get_localized_title(),
            'author': course.author.get_full_name() if course.author else 'Unknown',
            'author_id': course.author.id if course.author else None,
            'created_at': course.created_at,
            'app_label': 'resources',
            'model_name': 'course',
            'admin_url': f'/admin/resources/course/{course.id}/change/',
            'detail_url': course.get_absolute_url() if hasattr(course, 'get_absolute_url') else None,
            'extra_info': course.institution.name if course.institution else None,
        })
    
    # 4. Resources - Documents (Articles, Thesis, Memoir)
    for doc in Document.objects.filter(approval_status='pending').select_related('author'):
        doc_type = doc.get_document_type_display() if hasattr(doc, 'get_document_type_display') else 'Document'
        pending_items.append({
            'id': doc.id,
            'type': doc_type,
            'type_class': 'document',
            'title': doc.get_localized_title(),
            'author': doc.author.get_full_name() if doc.author else 'Unknown',
            'author_id': doc.author.id if doc.author else None,
            'created_at': doc.created_at,
            'app_label': 'resources',
            'model_name': 'document',
            'admin_url': f'/admin/resources/document/{doc.id}/change/',
            'detail_url': doc.get_absolute_url() if hasattr(doc, 'get_absolute_url') else None,
        })
    
    # 5. Projects
    for project in Project.objects.filter(approval_status='pending').select_related('coordinator', 'institution'):
        pending_items.append({
            'id': project.id,
            'type': 'Project',
            'type_class': 'project',
            'title': project.title,
            'author': project.coordinator.get_full_name() if project.coordinator else 'Unknown',
            'author_id': project.coordinator.id if project.coordinator else None,
            'created_at': project.created_at,
            'app_label': 'projects',
            'model_name': 'project',
            'admin_url': f'/admin/projects/project/{project.id}/change/',
            'detail_url': f'/projects/{project.id}/',
            'extra_info': project.institution.name if project.institution else None,
        })
    
    # 6. Forum Topics
    for topic in Topic.objects.filter(approval_status='pending').select_related('author'):
        pending_items.append({
            'id': topic.id,
            'type': 'Forum Topic',
            'type_class': 'topic',
            'title': topic.title,
            'author': topic.author.get_full_name() if topic.author else 'Unknown',
            'author_id': topic.author.id if topic.author else None,
            'created_at': topic.created_at,
            'app_label': 'forum',
            'model_name': 'topic',
            'admin_url': f'/admin/forum/topic/{topic.id}/change/',
            'detail_url': f'/forum/topic/{topic.id}/',
        })
    
    # 7. Events
    for event in Event.objects.filter(approval_status='pending').select_related('created_by'):
        pending_items.append({
            'id': event.id,
            'type': 'Event',
            'type_class': 'event',
            'title': event.title,
            'author': event.created_by.get_full_name() if event.created_by else 'Unknown',
            'author_id': event.created_by.id if event.created_by else None,
            'created_at': event.created_at,
            'app_label': 'events',
            'model_name': 'event',
            'admin_url': f'/admin/events/event/{event.id}/change/',
            'detail_url': f'/events/{event.id}/',
            'extra_info': f"{event.get_event_type_display()}" if hasattr(event, 'get_event_type_display') else None,
        })
    
    # Sort by created_at (newest first)
    pending_items.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Calculate statistics
    stats = {
        'total': len(pending_items),
        'by_type': {},
    }
    
    for item in pending_items:
        type_key = item['type']
        stats['by_type'][type_key] = stats['by_type'].get(type_key, 0) + 1
    
    context = {
        'pending_items': pending_items,
        'stats': stats,
    }
    
    return render(request, 'core/pending_content_dashboard.html', context)


@staff_member_required
def bulk_approve_content(request):
    """
    Bulk approve selected content from the dashboard.
    AJAX endpoint for quick approval.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
    
    import json
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        
        if not items:
            return JsonResponse({'success': False, 'error': 'No items selected'})
        
        approved_count = 0
        errors = []
        
        for item in items:
            app_label = item.get('app_label')
            model_name = item.get('model_name')
            item_id = item.get('id')
            
            try:
                # Get the model dynamically
                from django.apps import apps
                model = apps.get_model(app_label, model_name)
                obj = model.objects.get(pk=item_id)
                
                # Approve
                obj.approval_status = 'approved'
                obj.save(update_fields=['approval_status'])
                
                # Send notification (if system exists)
                try:
                    send_approval_notification(obj, request.user)
                except Exception as e:
                    logger.warning(f"Failed to send notification: {e}")
                
                approved_count += 1
                logger.info(f"[ADMIN_APPROVE] {app_label}.{model_name}#{item_id} approved by {request.user}")
                
            except Exception as e:
                errors.append(f"{model_name}#{item_id}: {str(e)}")
                logger.error(f"[ADMIN_APPROVE_ERROR] {app_label}.{model_name}#{item_id}: {e}")
        
        return JsonResponse({
            'success': True,
            'approved_count': approved_count,
            'errors': errors,
            'message': f'{approved_count} item(s) approved successfully'
        })
        
    except Exception as e:
        logger.error(f"[BULK_APPROVE_ERROR] {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
def bulk_reject_content(request):
    """
    Bulk reject selected content from the dashboard.
    AJAX endpoint for quick rejection.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
    
    import json
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        reason = data.get('reason', '')
        
        if not items:
            return JsonResponse({'success': False, 'error': 'No items selected'})
        
        rejected_count = 0
        errors = []
        
        for item in items:
            app_label = item.get('app_label')
            model_name = item.get('model_name')
            item_id = item.get('id')
            
            try:
                # Get the model dynamically
                from django.apps import apps
                model = apps.get_model(app_label, model_name)
                obj = model.objects.get(pk=item_id)
                
                # Reject
                obj.approval_status = 'rejected'
                obj.save(update_fields=['approval_status'])
                
                # Send notification (if system exists)
                try:
                    send_rejection_notification(obj, request.user, reason)
                except Exception as e:
                    logger.warning(f"Failed to send notification: {e}")
                
                rejected_count += 1
                logger.info(f"[ADMIN_REJECT] {app_label}.{model_name}#{item_id} rejected by {request.user}")
                
            except Exception as e:
                errors.append(f"{model_name}#{item_id}: {str(e)}")
                logger.error(f"[ADMIN_REJECT_ERROR] {app_label}.{model_name}#{item_id}: {e}")
        
        return JsonResponse({
            'success': True,
            'rejected_count': rejected_count,
            'errors': errors,
            'message': f'{rejected_count} item(s) rejected successfully'
        })
        
    except Exception as e:
        logger.error(f"[BULK_REJECT_ERROR] {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def send_approval_notification(obj, admin_user):
    """
    Send notification when content is approved.
    Uses the notifications app if available.
    """
    try:
        from notifications.services import NotificationService
        
        # Get author field dynamically
        author = None
        for field_name in ['author', 'coordinator', 'created_by']:
            if hasattr(obj, field_name):
                author = getattr(obj, field_name)
                break
        
        if not author:
            logger.warning(f"No author found for {obj.__class__.__name__}#{obj.pk}")
            return
        
        # Get content title
        if hasattr(obj, 'get_localized_title'):
            title = obj.get_localized_title()
        elif hasattr(obj, 'title'):
            title = obj.title
        else:
            title = 'Your content'
        
        # Get action URL
        action_url = obj.get_absolute_url() if hasattr(obj, 'get_absolute_url') else None
        
        NotificationService.create_notification(
            recipient=author,
            notification_type='CONTENT_APPROVED',
            title=_('Content Approved'),
            message=_('Your content "%(title)s" has been approved and is now publicly visible.'),
            related_object=obj,
            sender_id=admin_user.id,
            action_url=action_url,
            message_kwargs={'title': title}
        )
        
        logger.info(f"[NOTIFICATION] Approval notification sent to {author} for {obj.__class__.__name__}#{obj.pk}")
        
    except ImportError:
        logger.warning("NotificationService not available - skipping notification")
    except Exception as e:
        logger.error(f"[NOTIFICATION_ERROR] {e}")


def send_rejection_notification(obj, admin_user, reason=''):
    """
    Send notification when content is rejected.
    Uses the notifications app if available.
    """
    try:
        from notifications.services import NotificationService
        
        # Get author field dynamically
        author = None
        for field_name in ['author', 'coordinator', 'created_by']:
            if hasattr(obj, field_name):
                author = getattr(obj, field_name)
                break
        
        if not author:
            logger.warning(f"No author found for {obj.__class__.__name__}#{obj.pk}")
            return
        
        # Get content title
        if hasattr(obj, 'get_localized_title'):
            title = obj.get_localized_title()
        elif hasattr(obj, 'title'):
            title = obj.title
        else:
            title = 'Your content'
        
        # Get action URL
        action_url = obj.get_absolute_url() if hasattr(obj, 'get_absolute_url') else None
        
        # Build message
        if reason:
            message = _('Your content "%(title)s" has been rejected. Reason: %(reason)s')
            message_kwargs = {'title': title, 'reason': reason}
        else:
            message = _('Your content "%(title)s" has been rejected.')
            message_kwargs = {'title': title}
        
        NotificationService.create_notification(
            recipient=author,
            notification_type='CONTENT_REJECTED',
            title=_('Content Rejected'),
            message=message,
            related_object=obj,
            sender_id=admin_user.id,
            action_url=action_url,
            message_kwargs=message_kwargs
        )
        
        logger.info(f"[NOTIFICATION] Rejection notification sent to {author} for {obj.__class__.__name__}#{obj.pk}")
        
    except ImportError:
        logger.warning("NotificationService not available - skipping notification")
    except Exception as e:
        logger.error(f"[NOTIFICATION_ERROR] {e}")
