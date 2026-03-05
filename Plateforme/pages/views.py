from django.conf import settings
from django.apps import apps
from django.db import transaction
from django.urls import reverse
from django.core.mail import send_mail
from django.views.generic import TemplateView
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from pages.forms import AdminResponseForm, ContactForm, AdminUserCreateForm
from accounts.models import CustomUser
from events.models import Event
from resources.models import Corpus, NLPTool, Document, Course
from projects.models import Project, ProjectMember
from django.contrib.auth import get_user_model
from forum.models import Topic, ChatRoom, Message
from django.db.models.functions import TruncDate, TruncMonth
from notifications.models import Notification
from notifications.services import NotificationService
from QA.models import Post, Question
from django.db.models import Count, Sum
import datetime
import json
from urllib.parse import urlencode
from datetime import timedelta
from django.utils import timezone
from django.core.paginator import Paginator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db.models import QuerySet

User = get_user_model()


class HomePageView(TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Événements à venir
        context['events'] = Event.objects.filter(
            start_date__gte=now()
        ).order_by('start_date')[:3]
        
        # Compteurs pour les statistiques
        context['corpus_count'] = Corpus.objects.count()
        context['tools_count'] = NLPTool.objects.count()
        context['projects_count'] = Project.objects.filter(approval_status='approved').count()
        context['members_count'] = User.objects.count()
        
        # Posts populaires (les plus likés) - only approved
        context['popular_posts'] = Post.objects.filter(approval_status='approved').annotate(
            like_count=Count('likes')
        ).order_by('-like_count', '-created_at')[:3]

        # Ressources les plus vues - ONLY APPROVED
        most_viewed_resources = []

        # Récupérer les 5 corpus les plus vus (approved only)
        most_viewed_corpus = Corpus.objects.filter(approval_status='approved').order_by('-views_count')[:3]
        for resource in most_viewed_corpus:
            resource.resource_type_display = "Corpus"  # type: ignore
            most_viewed_resources.append(resource)

        # Récupérer les 5 outils NLP les plus vus (approved only)
        most_viewed_tools = NLPTool.objects.filter(approval_status='approved').order_by('-views_count')[:3]
        for resource in most_viewed_tools:
            resource.resource_type_display = "Tool"  # type: ignore
            most_viewed_resources.append(resource)

        # Récupérer les 5 documents les plus vus (approved only)
        most_viewed_documents = Document.objects.filter(approval_status='approved').order_by('-views_count')[:3]
        for resource in most_viewed_documents:
            resource.resource_type_display = getattr(resource, 'get_document_type_display', lambda: 'Document')()  # type: ignore
            most_viewed_resources.append(resource)

        # Récupérer les 5 cours les plus vus (approved only)
        most_viewed_courses = Course.objects.filter(approval_status='approved').order_by('-views_count')[:3]
        for resource in most_viewed_courses:
            resource.resource_type_display = "Course"  # type: ignore
            most_viewed_resources.append(resource)

        # Trier toutes les ressources les plus vues par nombre de vues (décroissant)
        context['most_viewed_resources'] = sorted(
            most_viewed_resources, 
            key=lambda x: x.views_count, 
            reverse=True
        )[:3]

        context['page'] = 'home'
        
        return context


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q
from .models import AdminActivityLog, ContactMessage, SecurityLog, Stats, UserStatusHistory
from institutions.models import Institution
import datetime
from accounts.forms import CustomUserChangeForm
from .security import (
    ROLE_ADMIN,
    ensure_moderator_group,
    get_user_role,
    has_admin_permission,
    log_admin_activity,
    sanitize_admin_text,
)


User = get_user_model()


def is_admin(user):
    """Allow admin panel access for admin + moderator roles."""
    return has_admin_permission(user, "view_dashboard")


def is_staff_user(user):
    return bool(user and user.is_authenticated and user.is_staff)


@login_required
@user_passes_test(is_staff_user)
def admin_dashboard(request):
    now_dt = timezone.now()
    today = now_dt.date()
    day_ago = now_dt - timedelta(days=1)
    week_ago = now_dt - timedelta(days=7)
    prev_week_start = now_dt - timedelta(days=14)
    month_ago = now_dt - timedelta(days=30)
    prev_month_start = now_dt - timedelta(days=60)

    def safe_model(app_label, model_name):
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            return None

    def model_fields(model):
        if not model:
            return set()
        return {f.name for f in model._meta.get_fields() if hasattr(f, 'name')}

    def count_recent(model, since_dt):
        if not model:
            return 0
        fields = model_fields(model)
        for date_field in ('created_at', 'creation_date', 'date_joined'):
            if date_field in fields:
                return model.objects.filter(**{f"{date_field}__gte": since_dt}).count()
        return 0

    def pending_queryset(model):
        if not model:
            return None
        fields = model_fields(model)
        if 'approval_status' in fields:
            return model.objects.filter(approval_status='pending')
        if 'is_approved' in fields:
            return model.objects.filter(is_approved=False)
        if 'status' in fields:
            return model.objects.filter(status='pending')
        return None

    def pending_count(model):
        qs = pending_queryset(model)
        return qs.count() if qs is not None else 0

    content_models = [
        {'slug': 'corpus', 'label': _('Corpus'), 'model': safe_model('resources', 'Corpus'), 'icon': 'fa-database', 'url': reverse('pages:admin_corpora')},
        {'slug': 'tools', 'label': _('Tools'), 'model': safe_model('resources', 'NLPTool'), 'icon': 'fa-screwdriver-wrench', 'url': reverse('pages:admin_tools')},
        {'slug': 'resources', 'label': _('Resources'), 'model': safe_model('resources', 'Document'), 'icon': 'fa-file-lines', 'url': reverse('pages:admin_publications')},
        {'slug': 'courses', 'label': _('Courses'), 'model': safe_model('resources', 'Course'), 'icon': 'fa-graduation-cap', 'url': reverse('pages:admin_courses')},
        {'slug': 'projects', 'label': _('Projects'), 'model': safe_model('projects', 'Project'), 'icon': 'fa-flask', 'url': reverse('pages:admin_projects')},
        {'slug': 'events', 'label': _('Events'), 'model': safe_model('events', 'Event'), 'icon': 'fa-calendar-days', 'url': reverse('pages:admin_calls')},
        {'slug': 'forum_topics', 'label': _('Forum Topics'), 'model': safe_model('forum', 'Topic'), 'icon': 'fa-comments', 'url': reverse('pages:admin_forum')},
        {'slug': 'institutions', 'label': _('Institutions'), 'model': safe_model('institutions', 'Institution'), 'icon': 'fa-building-columns', 'url': reverse('pages:admin_institutions')},
    ]

    UserModel = get_user_model()
    users_total = UserModel.objects.count()
    users_active_7d = UserModel.objects.filter(last_login__gte=week_ago).count()
    users_active_prev_7d = UserModel.objects.filter(last_login__gte=prev_week_start, last_login__lt=week_ago).count()
    users_new_today = UserModel.objects.filter(date_joined__date=today).count()
    users_new_yesterday = UserModel.objects.filter(date_joined__date=today - timedelta(days=1)).count()
    users_new_7d = UserModel.objects.filter(date_joined__gte=week_ago).count()
    users_new_30d = UserModel.objects.filter(date_joined__gte=month_ago).count()
    users_new_prev_30d = UserModel.objects.filter(date_joined__gte=prev_month_start, date_joined__lt=month_ago).count()
    users_staff = UserModel.objects.filter(is_staff=True).count()

    ActivityLogModel = safe_model('pages', 'ActivityLog') or AdminActivityLog
    BlockedUploadModel = safe_model('pages', 'BlockedUpload')

    if BlockedUploadModel:
        blocked_uploads_total = BlockedUploadModel.objects.count()
        blocked_uploads_24h = BlockedUploadModel.objects.filter(blocked_at__gte=day_ago).count()
    else:
        blocked_uploads_total = ActivityLogModel.objects.filter(action='blocked_upload').count()
        blocked_uploads_24h = ActivityLogModel.objects.filter(action='blocked_upload', occurred_at__gte=day_ago).count()

    security_events_24h = ActivityLogModel.objects.filter(occurred_at__gte=day_ago).count()
    security_events_prev_24h = ActivityLogModel.objects.filter(occurred_at__gte=day_ago - timedelta(days=1), occurred_at__lt=day_ago).count()
    logs_total = ActivityLogModel.objects.count()
    recent_logs = ActivityLogModel.objects.select_related('admin_user').order_by('-occurred_at')[:20]

    content_inventory = []
    pending_sections = []
    total_pending_reviews = 0
    pending_recent_7d = 0
    for item in content_models:
        model = item['model']
        total_count = model.objects.count() if model else 0
        recent_count = count_recent(model, week_ago)
        pending = pending_count(model)
        total_pending_reviews += pending
        pending_recent_7d += count_recent(model, week_ago) if pending else 0
        row = {
            **item,
            'total_count': total_count,
            'recent_count': recent_count,
            'pending_count': pending,
        }
        content_inventory.append(row)
        if pending > 0:
            pending_sections.append(row)

    chart_start = today - timedelta(days=29)
    signup_rows = (
        UserModel.objects.filter(date_joined__date__gte=chart_start)
        .annotate(day=TruncDate('date_joined'))
        .values('day')
        .annotate(total=Count('id'))
        .order_by('day')
    )
    signup_map = {r['day']: r['total'] for r in signup_rows}
    signup_labels = []
    signup_values = []
    for i in range(30):
        day = chart_start + timedelta(days=i)
        signup_labels.append(day.strftime('%Y-%m-%d'))
        signup_values.append(int(signup_map.get(day, 0)))

    recent_users = UserModel.objects.order_by('-date_joined')[:10]

    quick_actions = [
        {'label': _('Manage Users'), 'url': reverse('pages:admin_users'), 'icon': 'fa-users'},
        {'label': _('Moderate Publications'), 'url': reverse('pages:admin_publications'), 'icon': 'fa-book-open'},
        {'label': _('Review Projects'), 'url': reverse('pages:admin_projects'), 'icon': 'fa-flask'},
        {'label': _('Moderate Forum'), 'url': reverse('pages:admin_forum'), 'icon': 'fa-comments'},
        {'label': _('Review Events'), 'url': reverse('pages:admin_calls'), 'icon': 'fa-calendar-days'},
        {'label': _('Security Center'), 'url': reverse('pages:admin_security'), 'icon': 'fa-shield-halved'},
    ]

    def metric(label, value, delta, period, icon, tone):
        return {
            'label': label,
            'value': value,
            'delta': delta,
            'period': period,
            'icon': icon,
            'tone': tone,
        }

    context = {
        'page': 'Admin',
        'overview_metrics': [
            metric(_('Total Users'), users_total, users_new_30d, _('this month'), 'fa-users', 'blue'),
            metric(_('Active Users (7d)'), users_active_7d, users_active_7d - users_active_prev_7d, _('vs last 7 days'), 'fa-user-check', 'green'),
            metric(_('New Users Today'), users_new_today, users_new_today - users_new_yesterday, _('vs yesterday'), 'fa-user-plus', 'purple'),
            metric(_('Pending Reviews'), total_pending_reviews, pending_recent_7d, _('created in 7 days'), 'fa-hourglass-half', 'yellow'),
            metric(_('Security Events (24h)'), security_events_24h, security_events_24h - security_events_prev_24h, _('vs previous 24h'), 'fa-shield-halved', 'red'),
        ],
        'users_metrics': [
            metric(_('Total Users'), users_total, users_new_30d, _('this month'), 'fa-users', 'blue'),
            metric(_('New Today'), users_new_today, users_new_7d, _('new in 7 days'), 'fa-user-plus', 'purple'),
            metric(_('Active Users (7d)'), users_active_7d, users_active_7d - users_active_prev_7d, _('vs last 7 days'), 'fa-user-check', 'green'),
            metric(_('Staff Count'), users_staff, 0, _('staff accounts'), 'fa-user-shield', 'yellow'),
        ],
        'security_metrics': [
            metric(_('Blocked Uploads'), blocked_uploads_total, blocked_uploads_24h, _('in last 24h'), 'fa-ban', 'red'),
            metric(_('Events (24h)'), security_events_24h, security_events_24h - security_events_prev_24h, _('vs previous 24h'), 'fa-triangle-exclamation', 'yellow'),
            metric(_('Total Log Entries'), logs_total, 0, _('audit entries'), 'fa-clipboard-list', 'blue'),
        ],
        'content_inventory': content_inventory,
        'pending_sections': pending_sections,
        'has_pending': bool(pending_sections),
        'quick_actions': quick_actions,
        'recent_users': recent_users,
        'recent_logs': recent_logs,
        'signup_labels_json': json.dumps(signup_labels),
        'signup_values_json': json.dumps(signup_values),
    }
    return render(request, 'admin/dashboard.html', context)


@login_required
@user_passes_test(is_admin)
def admin_review_item_api(request, model_type, pk):
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    if model_type not in MODEL_MAP:
        return JsonResponse({'ok': False, 'error': 'Invalid model type'}, status=400)

    Model = MODEL_MAP[model_type]
    item = get_object_or_404(Model, pk=pk)

    def _get_first(names):
        for name in names:
            if hasattr(item, name):
                value = getattr(item, name)
                if value is not None:
                    return str(value)
        return ''

    author_name = '-'
    for attr in ('author', 'coordinator', 'creator', 'teacher', 'created_by'):
        u = getattr(item, attr, None)
        if not u:
            continue
        display = getattr(u, 'get_full_name_display', None)
        if callable(display):
            author_name = str(display())
            break
        author_name = str(getattr(u, 'full_name', None) or getattr(u, 'username', None) or getattr(u, 'email', '-'))
        break

    return JsonResponse({
        'ok': True,
        'item': {
            'id': str(item.pk),
            'model_type': model_type,
            'title': _get_first(['title', 'name']),
            'description': _get_first(['description', 'content']),
            'category': _get_first(['category', 'field', 'tool_type', 'document_type']),
            'author': author_name,
        }
    })


@login_required
@user_passes_test(is_admin)
def admin_review_save_api(request, model_type, pk):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    if model_type not in MODEL_MAP:
        return JsonResponse({'ok': False, 'error': 'Invalid model type'}, status=400)

    Model = MODEL_MAP[model_type]
    item = get_object_or_404(Model, pk=pk)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}

    updated_fields = []

    title = (payload.get('title') or '').strip()
    if title and hasattr(item, 'title'):
        setattr(item, 'title', title)
        updated_fields.append('title')
    elif title and hasattr(item, 'name'):
        setattr(item, 'name', title)
        updated_fields.append('name')

    description = (payload.get('description') or '').strip()
    if description and hasattr(item, 'description'):
        setattr(item, 'description', description)
        updated_fields.append('description')
    elif description and hasattr(item, 'content'):
        setattr(item, 'content', description)
        updated_fields.append('content')

    category = (payload.get('category') or '').strip()
    for field_name in ('category', 'field', 'tool_type', 'document_type'):
        if category and hasattr(item, field_name):
            setattr(item, field_name, category)
            updated_fields.append(field_name)
            break

    if updated_fields:
        item.save(update_fields=list(dict.fromkeys(updated_fields)))

    return JsonResponse({'ok': True, 'updated_fields': updated_fields})


@login_required
@user_passes_test(is_admin)
def admin_users(request):
    """Admin user management view"""
    filter_status = request.GET.get('status', '')
    search = request.GET.get('search', '').strip()
    
    # Type hint the queryset
    qs: 'QuerySet[CustomUser]' = CustomUser.objects.all().order_by('-date_joined')
    
    # Filtering
    if filter_status == 'active':
        qs = qs.filter(is_active=True, is_email_verified=True)
    elif filter_status == 'pending':
        qs = qs.filter(is_active=False, is_email_verified=True)
    elif filter_status == 'blocked':
        qs = qs.filter(is_active=False, is_email_verified=True)
    
    # Search
    if search:
        qs = qs.filter(
            Q(full_name__icontains=search) |
            Q(email__icontains=search) 
        )
    
    pending_users_count = CustomUser.objects.filter(
        is_active=False,
        is_email_verified=False
    ).count()
    
    context = {
        'users': qs,
        'pending_users_count': pending_users_count,
        'filter_status': filter_status,
        'search': search,
    }
    return render(request, 'admin/users.html', context)


@login_required
@user_passes_test(is_admin)
def admin_users_new(request):
    if get_user_role(request.user) != ROLE_ADMIN:
        messages.error(request, _("Only administrators can create users."))
        return redirect('pages:admin_users')

    ensure_moderator_group()

    if request.method == 'POST':
        form = AdminUserCreateForm(request.POST)
        if form.is_valid():
            user = form.save(created_by=request.user)
            log_admin_activity(
                user=request.user,
                request=request,
                action="create_user",
                target_type="user",
                target_id=str(user.id),
                details=f"role={get_user_role(user)};status={user.status}",
            )
            messages.success(
                request,
                _("User %(name)s has been created successfully.") % {'name': user.full_name or user.email},
            )
            return redirect('pages:admin_users')
        messages.error(request, _("Please fix the form errors."))
        return render(request, 'admin/users_new.html', {'form': form})

    return render(request, 'admin/users_new.html', {'form': AdminUserCreateForm()})


@login_required
@user_passes_test(is_admin)
@transaction.atomic
def admin_user_delete(request, user_id):
    user_obj: CustomUser = get_object_or_404(CustomUser, id=user_id)

    if user_obj == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect('pages:admin_users')

    if request.method == 'POST':
        UserStatusHistory.objects.create(
            user=user_obj,
            old_status=user_obj.status,
            new_status='deleted',
            changed_by=request.user,
            change_date=timezone.now(),
            reason='Account deleted by admin'
        )
        user_obj.delete()

        messages.success(request, f"The user {user_obj.full_name} has been successfully deleted.")
        return redirect('pages:admin_users')

    return render(request, 'admin/users_delete_confirm.html', {'user_obj': user_obj})


@login_required
@user_passes_test(is_admin)
@transaction.atomic
def admin_user_activate(request, user_id):
    """Vue pour activer un utilisateur."""
    user: CustomUser = get_object_or_404(CustomUser, id=user_id)
    
    if user.status == 'active':
        messages.info(request, f"The user {user.full_name} is already active.")
        return redirect('pages:admin_users')
    
    old_status = user.status
    user.is_active = True
    user.status = 'active'
    user.is_verified = True
    user.save()
    
    UserStatusHistory.objects.create(
        user=user,
        old_status=old_status,
        new_status='active',
        changed_by=request.user,
        change_date=timezone.now()
    )
    
    Notification.objects.create(
        recipient=user,
        title=_("Account activated"),
        message=_("Your account has been activated by an administrator. You can now access all features.")
    )
    
    messages.success(request, f"The user {user.full_name} has been successfully activated.")
    
    next_url = request.GET.get('next', reverse('pages:admin_users'))
    return redirect(next_url)


@login_required
@user_passes_test(is_admin)
def admin_user_block(request, user_id):
    """Vue pour bloquer un utilisateur."""
    user: CustomUser = get_object_or_404(CustomUser, id=user_id)
    
    if user == request.user:
        messages.error(request, "You cannot block your own account.")
        return redirect('pages:admin_users')
    
    if user.status == 'blocked':
        messages.info(request, f"The user {user.full_name} is already blocked.")
        return redirect('pages:admin_users')
    
    if request.method == 'POST':
        reason = sanitize_admin_text(request.POST.get('reason', ''), max_len=1000)
        old_status = user.status
        user.is_active = False
        user.status = 'blocked'
        user.save()
        
        UserStatusHistory.objects.create(
            user=user,
            old_status=old_status,
            new_status='blocked',
            changed_by=request.user,
            change_date=timezone.now(),
            reason=reason
        )
        
        Notification.objects.create(
            recipient=user,
            title=_("Blocked account"),
            message=_("Your account has been locked by an administrator. Please contact support if necessary.")
        )
        
        messages.success(request, f"The user {user.full_name} has been successfully blocked.")
        return redirect('pages:admin_users')
    
    return render(request, 'admin/block_confirm.html', {'user_obj': user})


@login_required
@user_passes_test(is_admin)
def admin_user_history(request, user_id):
    """Vue pour afficher l'historique des statuts d'un utilisateur."""
    user: CustomUser = get_object_or_404(CustomUser, id=user_id)
    
    status_filter = request.GET.get('status_filter', '')
    admin_filter = request.GET.get('admin_filter', '')
    period_filter = request.GET.get('period_filter', '')

    history_qs = UserStatusHistory.objects.filter(user=user).order_by('-change_date')

    if status_filter:
        history_qs = history_qs.filter(new_status=status_filter)
    if admin_filter:
        history_qs = history_qs.filter(changed_by__id=admin_filter)

    today = timezone.now().date()
    if period_filter == 'day':
        history_qs = history_qs.filter(change_date__date=today)
    elif period_filter == 'week':
        start_week = today - datetime.timedelta(days=today.weekday())
        history_qs = history_qs.filter(change_date__date__gte=start_week)
    elif period_filter == 'month':
        start_month = today.replace(day=1)
        history_qs = history_qs.filter(change_date__date__gte=start_month)

    total_changes = UserStatusHistory.objects.filter(user=user).count()
    activations = UserStatusHistory.objects.filter(user=user, new_status='active').count()
    blocks = UserStatusHistory.objects.filter(user=user, new_status='blocked').count()

    seven_days_ago = timezone.now() - datetime.timedelta(days=7)
    recent_changes_count = UserStatusHistory.objects.filter(user=user, change_date__gte=seven_days_ago).count()
    
    all_admins: 'QuerySet[CustomUser]' = CustomUser.objects.filter(is_staff=True).order_by('full_name')

    context = {
        'user_obj': user,
        'recent_history': history_qs,
        'total_changes': total_changes,
        'activations': activations,
        'blocks': blocks,
        'recent_changes': recent_changes_count,
        'status_filter': status_filter,
        'admin_filter': int(admin_filter) if admin_filter else '',
        'period_filter': period_filter,
        'all_admins': all_admins,
    }

    return render(request, 'admin/history.html', context)


@login_required
@user_passes_test(is_admin)
def admin_user_edit(request, user_id):
    """Admin view to edit user details"""
    user_obj: CustomUser = get_object_or_404(CustomUser, id=user_id)

    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, request.FILES, instance=user_obj)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                _("The user %(name)s has been updated.") % {'name': user_obj.full_name or user_obj.email},
            )
            return redirect('pages:admin_users')
    else:
        form = CustomUserChangeForm(instance=user_obj)

    context = {
        'form': form,
        'user_obj': user_obj,
    }
    return render(request, 'admin/user_edit.html', context)


@login_required
@user_passes_test(is_admin)
def admin_user_status(request, user_id, status):
    """Change user status (approve, block, etc.)"""
    allowed_statuses = {code for code, _ in CustomUser.STATUS_CHOICES}  # type: ignore[attr-defined]
    if status not in allowed_statuses:
        messages.error(request, _("Unknown status %(status)s") % {'status': status})
        return redirect('pages:admin_users')

    user_obj: CustomUser = get_object_or_404(CustomUser, id=user_id)
    old_status = user_obj.status
    reason = sanitize_admin_text(request.POST.get('reason', ''), max_len=1000)

    user_obj.status = status
    user_obj.is_active = status == 'active'
    if status == 'active':
        user_obj.is_verified = True
    elif status == 'blocked':
        user_obj.is_verified = False
    user_obj.save(update_fields=['status', 'is_active', 'is_verified'])

    UserStatusHistory.objects.create(
        user=user_obj,
        old_status=old_status,
        new_status=status,
        changed_by=request.user,
        reason=reason or None,
    )

    messages.success(
        request,
        _("The user %(name)s has been marked as %(status)s.") % {
            'name': user_obj.full_name or user_obj.email,
            'status': dict(CustomUser.STATUS_CHOICES).get(status, status),  # type: ignore[attr-defined]
        }
    )
    return redirect('pages:admin_users')


@login_required
@user_passes_test(is_admin)
def admin_publications(request):
    """Admin publications management with approval workflow"""
    publication_type = request.GET.get('document_type', '')
    search = request.GET.get('search', '').strip()
    tab = request.GET.get('tab', 'approved')  # Default to approved tab

    base_qs = Document.objects.prefetch_related('authors').select_related('author').order_by('-creation_date')

    if publication_type:
        base_qs = base_qs.filter(document_type=publication_type)
    if search:
        base_qs = base_qs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(keywords__icontains=search) |
            Q(authors__full_name__icontains=search)
        ).distinct()

    # Separate pending and approved items
    pending_publications = base_qs.filter(approval_status='pending')
    approved_publications = base_qs.filter(approval_status='approved')
    
    # Get counts for badges
    pending_count = pending_publications.count()
    approved_count = approved_publications.count()

    context = {
        'publications': approved_publications if tab == 'approved' else pending_publications,
        'pending_publications': pending_publications,
        'approved_publications': approved_publications,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'active_tab': tab,
        'filter_publication_type': publication_type,
        'search': search,
        'model_type': 'document',
    }
    return render(request, 'admin/publications.html', context)


@login_required
@user_passes_test(is_admin)
def admin_corpora(request):
    """Admin corpora management with approval workflow"""
    field = request.GET.get('field', '')
    file_format = request.GET.get('file_format', '')
    search = request.GET.get('search', '').strip()
    tab = request.GET.get('tab', 'approved')

    base_qs = Corpus.objects.select_related('author').order_by('-creation_date')

    if field:
        base_qs = base_qs.filter(field=field)
    if file_format:
        base_qs = base_qs.filter(file_format__iexact=file_format)
    if search:
        base_qs = base_qs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(author__full_name__icontains=search)
        )

    # Separate pending and approved items
    pending_corpora = base_qs.filter(approval_status='pending')
    approved_corpora = base_qs.filter(approval_status='approved')
    
    pending_count = pending_corpora.count()
    approved_count = approved_corpora.count()

    available_fields = sorted(set(Corpus.objects.exclude(field='').values_list('field', flat=True)))
    available_formats = sorted(set(Corpus.objects.exclude(file_format='').values_list('file_format', flat=True)))

    context = {
        'corpora': approved_corpora if tab == 'approved' else pending_corpora,
        'pending_corpora': pending_corpora,
        'approved_corpora': approved_corpora,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'active_tab': tab,
        'filter_field': field,
        'filter_format': file_format,
        'search': search,
        'available_fields': available_fields,
        'available_formats': available_formats,
        'model_type': 'corpus',
    }
    return render(request, 'admin/corpora.html', context)


@login_required
@user_passes_test(is_admin)
def admin_tools(request):
    """Admin tools management with approval workflow"""
    tool_type = request.GET.get('tool_type', '')
    supported_language = request.GET.get('language', '')
    search = request.GET.get('search', '').strip()
    tab = request.GET.get('tab', 'approved')

    base_qs = NLPTool.objects.select_related('author').order_by('-creation_date')

    if tool_type:
        base_qs = base_qs.filter(tool_type=tool_type)
    if supported_language:
        base_qs = base_qs.filter(supported_languages=supported_language)
    if search:
        base_qs = base_qs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(author__full_name__icontains=search)
        )

    # Separate pending and approved items
    pending_tools = base_qs.filter(approval_status='pending')
    approved_tools = base_qs.filter(approval_status='approved')
    
    pending_count = pending_tools.count()
    approved_count = approved_tools.count()

    context = {
        'tools': approved_tools if tab == 'approved' else pending_tools,
        'pending_tools': pending_tools,
        'approved_tools': approved_tools,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'active_tab': tab,
        'filter_tool_type': tool_type,
        'filter_language': supported_language,
        'search': search,
        'model_type': 'nlptool',
    }
    return render(request, 'admin/tools.html', context)


@login_required
@user_passes_test(is_admin)
def admin_projects(request):
    """Admin projects management with approval workflow"""
    status = request.GET.get('status', '')
    search = request.GET.get('search', '').strip()
    active_tab = request.GET.get('tab', 'approved')

    base_qs = Project.objects.select_related('institution', 'coordinator')

    # Build filtered queryset based on active tab
    if active_tab == 'pending':
        projects = base_qs.filter(approval_status='pending')
    else:
        projects = base_qs.filter(approval_status='approved')

    if status:
        projects = projects.filter(status=status)
    if search:
        projects = projects.filter(
            Q(title__icontains=search) |
            Q(title_ar__icontains=search) |
            Q(title_en__icontains=search) |
            Q(description__icontains=search) |
            Q(coordinator__full_name__icontains=search)
        )

    projects = projects.order_by('-created_at')

    all_projects = Project.objects.all()
    total_count = all_projects.count()
    in_progress_count = all_projects.filter(status='ongoing').count()
    completed_count = all_projects.filter(status='completed').count()
    pending_count = all_projects.filter(approval_status='pending').count()
    approved_count = all_projects.filter(approval_status='approved').count()

    today = timezone.now().date()
    last_month = today - timedelta(days=30)
    two_months_ago = today - timedelta(days=60)

    projects_this_month = all_projects.filter(created_at__gte=last_month).count()
    projects_last_month = all_projects.filter(created_at__gte=two_months_ago, created_at__lt=last_month).count()
    projects_growth = ((projects_this_month - projects_last_month) / projects_last_month * 100) if projects_last_month else (100 if projects_this_month else 0)

    completed_this_month = all_projects.filter(status='completed', created_at__gte=last_month).count()
    completed_last_month = all_projects.filter(status='completed', created_at__gte=two_months_ago, created_at__lt=last_month).count()
    completed_growth = ((completed_this_month - completed_last_month) / completed_last_month * 100) if completed_last_month else (100 if completed_this_month else 0)

    recent_completed = all_projects.filter(
        status='completed',
        date_end__isnull=False,
        date_start__isnull=False,
        date_end__gte=last_month
    )
    previous_completed = all_projects.filter(
        status='completed',
        date_end__isnull=False,
        date_start__isnull=False,
        date_end__lt=last_month,
        date_end__gte=two_months_ago
    )

    def average_duration(projects_qs):
        durations = [
            proj.date_end - proj.date_start
            for proj in projects_qs
            if proj.date_end and proj.date_start and proj.date_end >= proj.date_start
        ]
        if not durations:
            return timedelta(0)
        return sum(durations, timedelta(0)) / len(durations)

    avg_duration_current = average_duration(recent_completed)
    avg_duration_previous = average_duration(previous_completed)
    duration_diff_days = (avg_duration_current - avg_duration_previous).days

    if duration_diff_days > 0:
        duration_trend_text = f"+{duration_diff_days}j {_('vs previous period')}"
        duration_trend_class = 'trend-down'
    elif duration_diff_days < 0:
        duration_trend_text = f"{duration_diff_days}j {_('vs previous period')}"
        duration_trend_class = 'trend-up'
    else:
        duration_trend_text = _("Stable")
        duration_trend_class = 'trend-neutral'

    context = {
        'projects': projects,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'active_tab': active_tab,
        'filter_status': status,
        'search': search,
        'projects_growth': round(projects_growth, 2),
        'in_progress_count': in_progress_count,
        'completed_count': completed_count,
        'total_count': total_count,
        'completed_growth': round(completed_growth, 2),
        'average_duration_display_days': avg_duration_current.days if avg_duration_current else 0,
        'duration_trend_text': duration_trend_text,
        'duration_trend_class': duration_trend_class,
        'model_type': 'project',
    }
    return render(request, 'admin/projects.html', context)


@login_required
@user_passes_test(is_admin)
def admin_courses(request):
    """Admin courses management with approval workflow"""
    level = request.GET.get('level', '')
    field = request.GET.get('field', '')
    search = request.GET.get('search', '').strip()

    base_qs = Course.objects.select_related('teacher', 'institution').order_by('-creation_date')
    if level:
        base_qs = base_qs.filter(academic_level=level)
    if field:
        base_qs = base_qs.filter(field=field)
    if search:
        base_qs = base_qs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(teacher__full_name__icontains=search)
        )

    # Courses admin section: no approval workflow (manage all courses directly)
    pending_courses = Course.objects.none()
    approved_courses = base_qs
    pending_count = 0
    approved_count = approved_courses.count()

    today = timezone.now().date()
    last_month = today - timedelta(days=30)
    two_months_ago = today - timedelta(days=60)

    all_courses = Course.objects.all()
    total_courses_count = all_courses.count()
    courses_this_month_count = all_courses.filter(creation_date__gte=last_month).count()
    courses_last_month_count = all_courses.filter(creation_date__gte=two_months_ago, creation_date__lt=last_month).count()
    courses_growth = ((courses_this_month_count - courses_last_month_count) / courses_last_month_count * 100) if courses_last_month_count else (100 if courses_this_month_count else 0)

    if courses_growth > 0:
        growth_class = 'trend-up'
    elif courses_growth < 0:
        growth_class = 'trend-down'
    else:
        growth_class = 'trend-neutral'

    context = {
        'pending_courses': pending_courses,
        'approved_courses': approved_courses,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'active_tab': 'approved',
        'filter_level': level,
        'filter_field': field,
        'search': search,
        'total_courses_count': total_courses_count,
        'courses_this_month_count': courses_this_month_count,
        'courses_growth': round(courses_growth, 2),
        'courses_growth_class': growth_class,
        'model_type': 'course',
    }
    return render(request, 'admin/courses.html', context)


@login_required
@user_passes_test(is_admin)
def admin_forum(request):
    """Admin forum management with approval workflow"""
    status = request.GET.get('status', '')
    search = request.GET.get('search', '').strip()
    tab = request.GET.get('tab', 'approved')
    page_number = request.GET.get('page')

    base_qs = Topic.objects.prefetch_related('chatrooms__messages').annotate(
        total_messages=Count('chatrooms__messages')
    ).order_by('-created_at')

    if search:
        base_qs = base_qs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(creator__full_name__icontains=search)
        )

    pending_topics = base_qs.filter(approval_status='pending')
    approved_base = base_qs.filter(approval_status='approved')

    # open/closed filter applies only to approved topics
    if status == 'open':
        approved_base = approved_base.filter(is_closed=False)
    elif status == 'closed':
        approved_base = approved_base.filter(is_closed=True)

    approved_topics = approved_base
    pending_count = pending_topics.count()
    approved_count = approved_topics.count()

    # Paginate based on active tab
    if tab == 'pending':
        paginator = Paginator(pending_topics, 10)
    else:
        paginator = Paginator(approved_topics, 10)
    page_obj = paginator.get_page(page_number)

    context = {
        'topics': page_obj,
        'pending_topics': pending_topics,
        'approved_topics': approved_topics,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'active_tab': tab,
        'total_topics_count': Topic.objects.count(),
        'open_topics_count': Topic.objects.filter(is_closed=False, approval_status='approved').count(),
        'closed_topics_count': Topic.objects.filter(is_closed=True, approval_status='approved').count(),
        'total_messages_count': Message.objects.count(),
        'filter_status': status,
        'search': search,
        'model_type': 'topic',
    }
    return render(request, 'admin/forum.html', context)


@login_required
@user_passes_test(is_admin)
def admin_topic_detail(request, pk):
    """View topic details"""
    topic = get_object_or_404(Topic, pk=pk)
    chatrooms = topic.chatrooms.prefetch_related('messages', 'messages__user')  # type: ignore[attr-defined]
    return render(request, 'admin/topic_detail.html', {'topic': topic, 'chatrooms': chatrooms})


@login_required
@user_passes_test(is_admin)
def admin_topic_edit(request, pk):
    """Edit topic"""
    topic = get_object_or_404(Topic, pk=pk)
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        is_closed = request.POST.get('is_closed') == 'on'
        if not title:
            messages.error(request, _("Title cannot be empty."))
        else:
            topic.title = title
            topic.description = description or topic.description
            topic.is_closed = is_closed
            topic.save()
            messages.success(request, _("Topic updated successfully."))
            return redirect('pages:admin_topic_detail', pk=topic.pk)
    return render(request, 'admin/topic_edit.html', {'topic': topic})


@login_required
@user_passes_test(is_admin)
def admin_topic_delete(request, pk):
    """Delete topic"""
    topic = get_object_or_404(Topic, pk=pk)
    if request.method == 'POST':
        topic.delete()
        messages.success(request, _("Topic deleted successfully."))
        return redirect('pages:admin_forum')
    return render(request, 'admin/topic_delete.html', {'topic': topic})


@login_required
@user_passes_test(is_admin)
def admin_topic_toggle_status(request, pk):
    """Toggle topic status (open/closed)"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    topic = get_object_or_404(Topic, pk=pk)
    topic.is_closed = not topic.is_closed
    topic.save()
    return JsonResponse({
        'status': 'success',
        'is_closed': topic.is_closed,
        'message': _('Topic %(state)s successfully') % {'state': _('closed') if topic.is_closed else _('opened')}
    })


@login_required
@user_passes_test(is_admin)
def admin_institutions(request):
    """Admin institutions management (approval workflow disabled, like courses)."""
    country_id = request.GET.get('country', '')
    institution_type = request.GET.get('type', '')
    search = request.GET.get('search', '').strip()
    tab = 'approved'

    base_qs = Institution.objects.select_related('country').order_by('name')
    if country_id:
        base_qs = base_qs.filter(country__id=country_id)
    if institution_type:
        base_qs = base_qs.filter(type=institution_type)
    if search:
        base_qs = base_qs.filter(
            Q(name__icontains=search) |
            Q(acronym__icontains=search) |
            Q(description__icontains=search)
        )

    # Approval workflow disabled for institutions in admin section.
    has_approval = False
    pending_institutions = Institution.objects.none()
    approved_institutions = base_qs
    pending_count = 0
    approved_count = base_qs.count()

    countries = Institution.objects.values(
        'country_id',
        'country__name_en',
        'country__name_ar'
    ).distinct()

    context = {
        'institutions': approved_institutions if tab == 'approved' else pending_institutions,
        'pending_institutions': pending_institutions,
        'approved_institutions': approved_institutions,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'active_tab': tab,
        'countries': countries,
        'filter_country': country_id,
        'filter_type': institution_type,
        'search': search,
        'has_approval': has_approval,
        'model_type': 'institution',
    }
    return render(request, 'admin/institutions.html', context)


@login_required
@user_passes_test(is_admin)
def admin_news(request):
    """Admin news/posts management with approval workflow"""
    search = request.GET.get('search', '').strip()
    tab = request.GET.get('tab', 'approved')

    base_qs = Post.objects.select_related('author').order_by('-created_at')

    if search:
        base_qs = base_qs.filter(
            Q(title__icontains=search) |
            Q(title_ar__icontains=search) |
            Q(title_en__icontains=search) |
            Q(content__icontains=search) |
            Q(author__full_name__icontains=search)
        )

    # Separate pending and approved items
    pending_posts = base_qs.filter(approval_status='pending')
    approved_posts = base_qs.filter(approval_status='approved')
    
    pending_count = pending_posts.count()
    approved_count = approved_posts.count()

    context = {
        'posts': approved_posts if tab == 'approved' else pending_posts,
        'pending_posts': pending_posts,
        'approved_posts': approved_posts,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'active_tab': tab,
        'search': search,
        'model_type': 'post',
    }
    return render(request, 'admin/news.html', context)


@login_required
@user_passes_test(is_admin)
def admin_news_approve(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    post.approval_status = 'approved'
    post.save(update_fields=['approval_status'])
    return redirect('pages:admin_news')


@login_required
@user_passes_test(is_admin)
def admin_news_delete(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    post.delete()
    return redirect('pages:admin_news')


@login_required
@user_passes_test(is_admin)
def admin_news_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    return render(request, 'admin/news_view.html', {'post': post})


@login_required
@user_passes_test(is_admin)
def admin_calls(request):
    """Admin calls for papers and events management with approval workflow"""
    call_type = request.GET.get('call_type', '')
    timeline = request.GET.get('timeline', '')
    search = request.GET.get('search', '').strip()
    tab = request.GET.get('tab', 'approved')

    base_qs = Event.objects.select_related('organizer').order_by('-start_date')

    if call_type:
        base_qs = base_qs.filter(event_type=call_type)
    if timeline == 'upcoming':
        base_qs = base_qs.filter(start_date__gte=timezone.now().date())
    elif timeline == 'past':
        base_qs = base_qs.filter(end_date__lt=timezone.now().date())
    if search:
        base_qs = base_qs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(organizer__name__icontains=search)
        )

    pending_calls = base_qs.filter(approval_status='pending')
    approved_calls = base_qs.filter(approval_status='approved')

    pending_count = pending_calls.count()
    approved_count = approved_calls.count()

    context = {
        'calls': approved_calls if tab == 'approved' else pending_calls,
        'pending_calls': pending_calls,
        'approved_calls': approved_calls,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'active_tab': tab,
        'filter_call_type': call_type,
        'filter_timeline': timeline,
        'search': search,
        'model_type': 'event',
    }
    return render(request, 'admin/calls.html', context)


@login_required
@user_passes_test(is_admin)
def admin_statistics(request):
    """Admin statistics view"""
    start = request.GET.get('start_date', '')
    end = request.GET.get('end_date', '')

    if start:
        start_date = datetime.datetime.strptime(start, '%Y-%m-%d').date()
    else:
        start_date = (timezone.now() - datetime.timedelta(days=30)).date()

    if end:
        end_date = datetime.datetime.strptime(end, '%Y-%m-%d').date()
    else:
        end_date = timezone.now().date()

    stats_qs = Stats.objects.filter(date__gte=start_date, date__lte=end_date).order_by('date')

    today = timezone.now().date()
    last_month = today - datetime.timedelta(days=30)
    two_months_ago = today - datetime.timedelta(days=60)

    current_stats = {
        'users_count': CustomUser.objects.count(),
        'publications_count': Document.objects.count(),
        'corpora_count': Corpus.objects.count(),
        'tools_count': NLPTool.objects.count(),
        'projects_count': Project.objects.count(),
        'forum_posts_count': Topic.objects.count() + ChatRoom.objects.count(),
        'visits_count': stats_qs.aggregate(total=Sum('visits_count'))['total'] or 0,
        'active_projects_count': Project.objects.filter(status='ongoing').count(),
    }

    def growth(current_value, previous_value):
        if previous_value:
            return (current_value - previous_value) / previous_value * 100
        return 100 if current_value else 0

    users_this_month = CustomUser.objects.filter(date_joined__gte=last_month).count()
    users_last_month = CustomUser.objects.filter(date_joined__gte=two_months_ago, date_joined__lt=last_month).count()
    current_stats['users_growth'] = growth(users_this_month, users_last_month)

    resources_this_month = (
        Document.objects.filter(creation_date__gte=last_month).count() +
        Corpus.objects.filter(creation_date__gte=last_month).count() +
        NLPTool.objects.filter(creation_date__gte=last_month).count()
    )
    resources_last_month = (
        Document.objects.filter(creation_date__gte=two_months_ago, creation_date__lt=last_month).count() +
        Corpus.objects.filter(creation_date__gte=two_months_ago, creation_date__lt=last_month).count() +
        NLPTool.objects.filter(creation_date__gte=two_months_ago, creation_date__lt=last_month).count()
    )
    current_stats['resources_growth'] = growth(resources_this_month, resources_last_month)

    visits_previous_period = Stats.objects.filter(
        date__gte=start_date - datetime.timedelta(days=30),
        date__lt=start_date
    ).aggregate(total=Sum('visits_count'))['total'] or 0
    current_stats['visits_growth'] = growth(current_stats['visits_count'], visits_previous_period)

    projects_this_month = Project.objects.filter(created_at__gte=last_month).count()
    projects_last_month = Project.objects.filter(created_at__gte=two_months_ago, created_at__lt=last_month).count()
    current_stats['projects_growth'] = growth(projects_this_month, projects_last_month)

    forum_this_month = Topic.objects.filter(created_at__gte=last_month).count() + ChatRoom.objects.filter(created_at__gte=last_month).count()
    forum_last_month = Topic.objects.filter(created_at__gte=two_months_ago, created_at__lt=last_month).count() + ChatRoom.objects.filter(created_at__gte=two_months_ago, created_at__lt=last_month).count()
    current_stats['forum_growth'] = growth(forum_this_month, forum_last_month)

    chart_dates = [stat.date.strftime('%Y-%m-%d') for stat in stats_qs]
    users_data = [stat.users_count for stat in stats_qs]
    resources_data = [stat.publications_count + stat.corpora_count + stat.tools_count for stat in stats_qs]
    visits_data = [stat.visits_count for stat in stats_qs]

    user_regs = (
        CustomUser.objects.filter(date_joined__date__gte=start_date, date_joined__date__lte=end_date)
        .annotate(day=TruncDate('date_joined'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    user_reg_dates = [row['day'].strftime('%Y-%m-%d') for row in user_regs]
    user_reg_counts = [row['count'] for row in user_regs]

    top_resources = []
    for resource in Document.objects.filter(approval_status='approved').order_by('-views_count')[:2]:
        top_resources.append({'title': str(resource), 'views': resource.views_count})
    for resource in Corpus.objects.filter(approval_status='approved').order_by('-views_count')[:2]:
        top_resources.append({'title': str(resource), 'views': resource.views_count})
    for resource in NLPTool.objects.filter(approval_status='approved').order_by('-views_count')[:1]:
        top_resources.append({'title': str(resource), 'views': resource.views_count})
    top_resources.sort(key=lambda item: item['views'], reverse=True)
    top_resources = top_resources[:5]

    context = {
        'stats': stats_qs,
        'current_stats': current_stats,
        'start_date': start_date,
        'end_date': end_date,
        'chart_dates': json.dumps(chart_dates),
        'users_data': json.dumps(users_data),
        'resources_data': json.dumps(resources_data),
        'visits_data': json.dumps(visits_data),
        'user_reg_dates': json.dumps(user_reg_dates),
        'user_reg_counts': json.dumps(user_reg_counts),
        'top_resources': top_resources,
    }
    return render(request, 'admin/statistics.html', context)


@login_required
@user_passes_test(is_admin)
def admin_settings(request):
    """Admin settings view"""
    return render(request, 'admin/settings.html')


@login_required
@user_passes_test(is_admin)
def admin_security(request):
    """Admin security center: metrics + paginated security logs."""
    logs_qs = SecurityLog.objects.select_related('user').order_by('-created_at')
    paginator = Paginator(logs_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    last_24h = timezone.now() - timedelta(hours=24)
    context = {
        'page_obj': page_obj,
        'recent_logs': page_obj.object_list,
        'logs_count': logs_qs.count(),
        'failed_uploads_count': logs_qs.filter(action='blocked_upload').count(),
        'recent_security_events_count': logs_qs.filter(created_at__gte=last_24h).count(),
    }
    return render(request, 'admin/security.html', context)


@login_required
@user_passes_test(is_admin)
def admin_api_stats(request):
    """API endpoint for dashboard statistics"""
    today = timezone.now().date()
    last_month = today - datetime.timedelta(days=30)
    two_months_ago = today - datetime.timedelta(days=60)

    def growth(current_value, previous_value):
        if previous_value:
            return (current_value - previous_value) / previous_value * 100
        return 100 if current_value else 0

    users_count = CustomUser.objects.count()
    users_this_month = CustomUser.objects.filter(date_joined__gte=last_month).count()
    users_last_month = CustomUser.objects.filter(date_joined__gte=two_months_ago, date_joined__lt=last_month).count()

    resources_count = Document.objects.count() + Corpus.objects.count() + NLPTool.objects.count() + Course.objects.count()
    resources_this_month = (
        Document.objects.filter(creation_date__gte=last_month).count() +
        Corpus.objects.filter(creation_date__gte=last_month).count() +
        NLPTool.objects.filter(creation_date__gte=last_month).count()
    )
    resources_last_month = (
        Document.objects.filter(creation_date__gte=two_months_ago, creation_date__lt=last_month).count() +
        Corpus.objects.filter(creation_date__gte=two_months_ago, creation_date__lt=last_month).count() +
        NLPTool.objects.filter(creation_date__gte=two_months_ago, creation_date__lt=last_month).count()
    )

    projects_count = Project.objects.filter(status='ongoing').count()
    projects_this_month = Project.objects.filter(created_at__gte=last_month).count()
    projects_last_month = Project.objects.filter(created_at__gte=two_months_ago, created_at__lt=last_month).count()

    forum_posts_count = Topic.objects.count() + ChatRoom.objects.count()
    posts_this_month = Topic.objects.filter(created_at__gte=last_month).count() + ChatRoom.objects.filter(created_at__gte=last_month).count()
    posts_last_month = Topic.objects.filter(created_at__gte=two_months_ago, created_at__lt=last_month).count() + ChatRoom.objects.filter(created_at__gte=two_months_ago, created_at__lt=last_month).count()

    return JsonResponse({
        'users': {
            'count': users_count,
            'growth': growth(users_this_month, users_last_month),
        },
        'resources': {
            'count': resources_count,
            'growth': growth(resources_this_month, resources_last_month),
        },
        'projects': {
            'count': projects_count,
            'growth': growth(projects_this_month, projects_last_month),
        },
        'forum_posts': {
            'count': forum_posts_count,
            'growth': growth(posts_this_month, posts_last_month),
        },
    })


@login_required
@user_passes_test(is_admin)
def admin_api_recent_users(request):
    """API endpoint for recent users"""
    recent_users: 'QuerySet[CustomUser]' = CustomUser.objects.all().order_by('-date_joined')[:10]
    data = []

    for user in recent_users:
        data.append({
            'id': user.id,
            'username': user.get_full_name() or user.email,
            'email': user.email,
            'status': user.get_status_display(),
            'date_joined': user.date_joined.strftime('%Y-%m-%d'),
        })

    return JsonResponse({'users': data})


@login_required
@user_passes_test(is_admin)
def admin_api_recent_content(request):
    """API endpoint for recent content"""
    content_type = request.GET.get('type', 'all')

    if content_type == 'publications':
        items = Document.objects.prefetch_related('authors').order_by('-creation_date')[:10]
        data = [
            {
                'id': item.id,
                'title': item.title,
                'type': item.get_document_type_display(),  # type: ignore[attr-defined]
                'author': ", ".join(author.get_full_name() or author.email for author in item.authors.all()) or (item.author.get_full_name() if item.author else ''),
                'date': item.creation_date.strftime('%Y-%m-%d'),
            }
            for item in items
        ]
    elif content_type == 'corpus':
        items = Corpus.objects.select_related('author').order_by('-creation_date')[:10]
        data = [
            {
                'id': item.id,
                'title': item.title,
                'type': _('Corpus'),
                'author': item.author.get_full_name() if item.author else '',
                'date': item.creation_date.strftime('%Y-%m-%d'),
            }
            for item in items
        ]
    elif content_type == 'tools':
        items = NLPTool.objects.select_related('author').order_by('-creation_date')[:10]
        data = [
            {
                'id': item.id,
                'title': item.title,
                'type': item.get_tool_type_display(),
                'author': item.author.get_full_name() if item.author else '',
                'date': item.creation_date.strftime('%Y-%m-%d'),
            }
            for item in items
        ]
    elif content_type == 'projects':
        items = Project.objects.select_related('coordinator').order_by('-created_at')[:10]
        data = [
            {
                'id': item.id,
                'title': item.title,
                'type': _('Project'),
                'author': item.coordinator.get_full_name() if item.coordinator else '',
                'date': item.created_at.strftime('%Y-%m-%d'),
                'status': item.get_status_display(),  # type: ignore[attr-defined]
            }
            for item in items
        ]
    else:
        publications = Document.objects.prefetch_related('authors').order_by('-creation_date')[:5]
        corpora = Corpus.objects.select_related('author').order_by('-creation_date')[:5]
        tools = NLPTool.objects.select_related('author').order_by('-creation_date')[:5]

        data = []
        for item in publications:
            data.append({
                'id': item.id,
                'title': item.title,
                'type': _('Publication'),
                'author': ", ".join(author.get_full_name() or author.email for author in item.authors.all()) or (item.author.get_full_name() if item.author else ''),
                'date': item.creation_date.strftime('%Y-%m-%d'),
            })
        for item in corpora:
            data.append({
                'id': item.id,
                'title': item.title,
                'type': _('Corpus'),
                'author': item.author.get_full_name() if item.author else '',
                'date': item.creation_date.strftime('%Y-%m-%d'),
            })
        for item in tools:
            data.append({
                'id': item.id,
                'title': item.title,
                'type': _('Tool'),
                'author': item.author.get_full_name() if item.author else '',
                'date': item.creation_date.strftime('%Y-%m-%d'),
            })
        data.sort(key=lambda entry: entry['date'], reverse=True)
        data = data[:10]

    return JsonResponse({'content': data})


def contact_view(request):
    """Public contact form view"""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            contact_message = form.save(commit=False)
            if request.user.is_authenticated:
                contact_message.user = request.user
            contact_message.save()

            try:
                default_from = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
                admin_email = getattr(settings, 'ADMIN_EMAIL', None)
                if default_from and admin_email:
                    send_mail(
                        subject=f"[Arabic NLP Platform] New Contact Message: {contact_message.get_subject_display()}",
                        message=f"New message from {contact_message.name} ({contact_message.email})\n\n{contact_message.message}",
                        from_email=default_from,
                        recipient_list=[admin_email],
                        fail_silently=True,
                    )
            except Exception:
                pass

            messages.success(request, _('Your message has been sent successfully. We will get back to you soon.'))
            return redirect('contact:contact')
    else:
        form = ContactForm()
        if request.user.is_authenticated:
            form.initial['name'] = request.user.full_name or request.user.get_username()
            form.initial['email'] = request.user.email

    return render(request, 'contact/contact.html', {
        'form': form,
        'page': 'contact'
    })


@login_required
@user_passes_test(is_admin)
def admin_contact_list(request):
    """View to list contact messages in the admin"""
    status_filter = request.GET.get('status', '')
    subject_filter = request.GET.get('subject', '')
    search_query = request.GET.get('search', '').strip()

    messages_qs = ContactMessage.objects.select_related('user').order_by('-created_at')
    if status_filter:
        messages_qs = messages_qs.filter(status=status_filter)
    if subject_filter:
        messages_qs = messages_qs.filter(subject=subject_filter)
    if search_query:
        messages_qs = messages_qs.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(message__icontains=search_query)
        )

    paginator = Paginator(messages_qs, 20)
    page_number = request.GET.get('page')
    messages_page = paginator.get_page(page_number)

    stats_summary = {
        'total': ContactMessage.objects.count(),
        'pending': ContactMessage.objects.filter(status='pending').count(),
        'read': ContactMessage.objects.filter(status='read').count(),
        'replied': ContactMessage.objects.filter(status='replied').count(),
        'closed': ContactMessage.objects.filter(status='closed').count(),
    }

    context = {
        'messages': messages_page,
        'stats': stats_summary,
        'status_filter': status_filter,
        'subject_filter': subject_filter,
        'search_query': search_query,
        'status_choices': ContactMessage.STATUS_CHOICES,
        'subject_choices': ContactMessage.SUBJECT_CHOICES,
    }
    return render(request, 'admin/contact_list.html', context)


@login_required
@user_passes_test(is_admin)
def admin_contact_detail(request, pk):
    """View to read and reply to a contact message"""
    contact_message = get_object_or_404(ContactMessage, pk=pk)

    if contact_message.status == 'pending':
        contact_message.status = 'read'
        contact_message.save(update_fields=['status'])

    if request.method == 'POST':
        form = AdminResponseForm(request.POST, instance=contact_message)
        if form.is_valid():
            response = form.save(commit=False)
            response.responded_by = request.user
            response.responded_at = timezone.now()
            if response.admin_response and response.status != 'replied':
                response.status = 'replied'
            response.save()

            if response.admin_response:
                try:
                    default_from = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
                    if default_from:
                        send_mail(
                            subject=f"[Arabic NLP Platform] Response to your message: {contact_message.get_subject_display()}",  # type: ignore[attr-defined]
                            message=f"Hello {contact_message.name},\n\n{response.admin_response}\n\nBest regards,\nArabic NLP Platform Team",
                            from_email=default_from,
                            recipient_list=[contact_message.email],
                            fail_silently=True,
                        )
                    messages.success(request, _('Response sent successfully.'))
                except Exception:
                    messages.warning(request, _('Response saved but email could not be sent.'))
            else:
                messages.success(request, _('Status updated successfully.'))
            return redirect('contact:admin_contact_detail', pk=pk)
    else:
        form = AdminResponseForm(instance=contact_message)

    return render(request, 'admin/contact_detail.html', {
        'contact_message': contact_message,
        'form': form,
    })


# ============================================
# APPROVAL WORKFLOW HANDLERS
# ============================================

MODEL_MAP = {
    'document': Document,
    'corpus': Corpus,
    'nlptool': NLPTool,
    'course': Course,
    'project': Project,
    'topic': Topic,
    'event': Event,
    'post': Post,
    'institution': Institution,
}

REDIRECT_MAP = {
    'document': 'pages:admin_publications',
    'corpus': 'pages:admin_corpora',
    'nlptool': 'pages:admin_tools',
    'course': 'pages:admin_courses',
    'project': 'pages:admin_projects',
    'topic': 'pages:admin_forum',
    'event': 'pages:admin_calls',
    'post': 'pages:admin_news',
    'institution': 'pages:admin_institutions',
}

# Translation field requirements for each model
TRANSLATION_FIELDS = {
    'document': {'title': ('title_ar', 'title_en'), 'description': ('description_ar', 'description_en')},
    'corpus': {'title': ('title_ar', 'title_en'), 'description': ('description_ar', 'description_en')},
    'nlptool': {'title': ('title_ar', 'title_en'), 'description': ('description_ar', 'description_en')},
    'course': {'title': ('title_ar', 'title_en'), 'description': ('description_ar', 'description_en')},
    'project': {'title': ('title_ar', 'title_en'), 'description': ('description_ar', 'description_en')},
    'topic': {'title': ('title_ar', 'title_en'), 'description': ('description_ar', 'description_en')},
    'event': {
        'title': ('title_ar', 'title_en'),
        'description': ('description_ar', 'description_en'),
        'location': ('location_ar', 'location_en')
    },
    'post': {'title': ('title_ar', 'title_en'), 'content': ('content_ar', 'content_en')},
    'institution': {'name': ('name_ar', 'name_en'), 'description': ('description_ar', 'description_en')},
}


def validate_translations(item, model_type):
    """
    Validate that all required translation fields are filled.
    Returns (is_valid, list_of_missing_fields)
    """
    fields_config = TRANSLATION_FIELDS.get(model_type, {})
    missing_fields = []
    
    for field_name, (ar_field, en_field) in fields_config.items():
        ar_value = getattr(item, ar_field, None)
        en_value = getattr(item, en_field, None)
        
        # Both languages must have a value
        if not ar_value or not str(ar_value).strip():
            missing_fields.append(f"{field_name} (Arabic)")
        if not en_value or not str(en_value).strip():
            missing_fields.append(f"{field_name} (English)")
    
    return len(missing_fields) == 0, missing_fields


# Edit URL mapping for admin review workflow
EDIT_URL_MAP = {
    'document': ('resources:resource-update', {'type': 'article'}),
    'corpus': ('resources:resource-update', {'type': 'corpus'}),
    'nlptool': ('resources:resource-update', {'type': 'tool'}),
    'course': ('resources:resource-update', {'type': 'course'}),
    'project': ('projects:project_update', {}),
    'topic': ('forum:topic-update', {}),
    'event': ('events:event_update', {}),
    'post': ('QA:edit_post', {'post_id': None}),  # post_id will be set separately
    'institution': ('institutions:institution_update', {}),
}


def get_edit_url(model_type, pk):
    """Get the edit URL for a given model type and pk."""
    url_info = EDIT_URL_MAP.get(model_type)
    if not url_info:
        return reverse('pages:admin_dashboard')
    
    url_name, extra_kwargs = url_info
    
    # Handle special case for posts which use post_id instead of pk
    if model_type == 'post':
        kwargs = {'post_id': pk}
    elif model_type == 'document':
        # Determine the actual document subtype instead of hardcoding 'article'
        from resources.models import Document
        try:
            doc = Document.objects.get(pk=pk)
            doc_type = doc.document_type or 'article'
        except Document.DoesNotExist:
            doc_type = 'article'
        kwargs = {'pk': pk, 'type': doc_type}
    else:
        kwargs = {'pk': pk}
        kwargs.update(extra_kwargs)
    
    return reverse(url_name, kwargs=kwargs)


def get_view_url(model_type, pk):
    """Get the details/read-only URL for a given model type and pk."""
    if model_type == 'document':
        from resources.models import Document
        try:
            doc = Document.objects.get(pk=pk)
            doc_type = doc.document_type or 'article'
        except Document.DoesNotExist:
            doc_type = 'article'
        return reverse('resources:resource-detail', kwargs={'type': doc_type, 'pk': pk})

    if model_type == 'corpus':
        return reverse('resources:resource-detail', kwargs={'type': 'corpus', 'pk': pk})

    if model_type == 'nlptool':
        return reverse('resources:resource-detail', kwargs={'type': 'tool', 'pk': pk})

    if model_type == 'course':
        return reverse('resources:resource-detail', kwargs={'type': 'course', 'pk': pk})

    if model_type == 'project':
        return reverse('projects:project_detail', kwargs={'pk': pk})

    if model_type == 'event':
        return reverse('events:event_detail', kwargs={'pk': pk})

    if model_type == 'post':
        return reverse('pages:admin_news_view', kwargs={'post_id': pk})

    # Topic has no dedicated detail template; keep review mode (read-only in template)
    if model_type == 'topic':
        return reverse('pages:admin_approve_item', kwargs={'model_type': model_type, 'pk': pk})

    return reverse('pages:admin_dashboard')


@login_required
@user_passes_test(is_admin)
def admin_view_item(request, model_type, pk):
    if model_type not in MODEL_MAP:
        messages.error(request, _("Invalid model type."))
        return redirect('pages:admin_dashboard')
    view_url = get_view_url(model_type, pk)
    review_qs = urlencode({
        'admin_review': '1',
        'review_model': model_type,
        'review_pk': str(pk),
    })
    separator = '&' if '?' in view_url else '?'
    return redirect(f"{view_url}{separator}{review_qs}")


@login_required
@user_passes_test(is_admin)
def admin_approve_item(request, model_type, pk):
    """
    Redirect admin to the edit page for reviewing/editing before approval.
    After editing, admin can use the 'Approve & Publish' button.
    """
    # For POST requests, this is the actual approval (called from edit page's "Approve & Publish" button)
    if request.method == 'POST':
        if model_type not in MODEL_MAP:
            messages.error(request, _("Invalid model type."))
            return redirect('pages:admin_dashboard')
        
        Model = MODEL_MAP[model_type]
        item = get_object_or_404(Model, pk=pk)
        
        # TRANSLATION CHECK: Warn if translations are incomplete, but do not block approval
        is_valid, missing_fields = validate_translations(item, model_type)
        if not is_valid:
            missing_str = ", ".join(missing_fields)
            messages.warning(
                request,
                _("Approved with incomplete translations (%(fields)s). Please complete bilingual fields later.") % {'fields': missing_str}
            )

        item.approval_status = 'approved'
        item.save(update_fields=['approval_status'])
        
        # Create notification to the author
        author = getattr(item, 'author', None) or getattr(item, 'coordinator', None) or getattr(item, 'creator', None) or getattr(item, 'created_by', None)
        title = getattr(item, 'title', str(item))
        
        if author:
            NotificationService.create_notification(
                recipient=author,
                notification_type='POST_APPROVED',
                title=_("Your submission has been approved"),
                message=_("Your submission '%(title)s' has been approved and is now visible to the public."),
                message_kwargs={'title': title}
            )
        
        messages.success(request, _("'%(title)s' has been approved and published.") % {'title': title})
        redirect_url = REDIRECT_MAP.get(model_type, 'pages:admin_dashboard')
        return redirect(f"{reverse(redirect_url)}?tab=pending")
    
    # For GET requests (clicking the Review button), redirect to edit page
    if model_type not in MODEL_MAP:
        messages.error(request, _("Invalid model type."))
        return redirect('pages:admin_dashboard')
    
    Model = MODEL_MAP[model_type]
    item = get_object_or_404(Model, pk=pk)
    title = getattr(item, 'title', str(item))
    
    edit_mode = request.GET.get('mode') == 'edit'
    if edit_mode:
        messages.info(request, _("Edit '%(title)s' and save your changes.") % {'title': title})
    else:
        messages.info(request, _("Review and edit '%(title)s'. Click 'Approve & Publish' when ready.") % {'title': title})

    # Redirect to the edit page with review context (or edit-only mode)
    edit_url = get_edit_url(model_type, pk)
    if edit_mode:
        review_qs = urlencode({
            'edit_only': '1',
            'review_model': model_type,
            'review_pk': str(pk),
        })
    else:
        review_qs = urlencode({
            'review': '1',
            'review_model': model_type,
            'review_pk': str(pk),
            'review_approve_url': reverse('pages:admin_approve_item', kwargs={'model_type': model_type, 'pk': pk}),
            'review_reject_url': reverse('pages:admin_reject_item', kwargs={'model_type': model_type, 'pk': pk}),
        })
    separator = '&' if '?' in edit_url else '?'
    return redirect(f"{edit_url}{separator}{review_qs}")


@login_required
@user_passes_test(is_admin)
def admin_reject_item(request, model_type, pk):
    """Reject and delete a pending item."""
    # Require POST for security (state-changing operation)
    if request.method != 'POST':
        messages.warning(request, _("Please use the reject button to reject items."))
        redirect_url = REDIRECT_MAP.get(model_type, 'pages:admin_dashboard')
        return redirect(f"{reverse(redirect_url)}?tab=pending")
    
    if model_type not in MODEL_MAP:
        messages.error(request, _("Invalid model type."))
        return redirect('pages:admin_dashboard')
    
    Model = MODEL_MAP[model_type]
    item = get_object_or_404(Model, pk=pk)
    
    # Get author before deletion
    author = getattr(item, 'author', None) or getattr(item, 'coordinator', None) or getattr(item, 'creator', None) or getattr(item, 'created_by', None)
    title = getattr(item, 'title', str(item))
    
    # Create notification to the author
    if author:
        NotificationService.create_notification(
            recipient=author,
            notification_type='POST_REJECTED',
            title=_("Your submission has been rejected"),
            message=_("Your submission '%(title)s' has been rejected and removed."),
            message_kwargs={'title': title}
        )
    
    item.delete()
    
    messages.warning(request, _("'%(title)s' has been rejected and deleted.") % {'title': title})
    redirect_url = REDIRECT_MAP.get(model_type, 'pages:admin_dashboard')
    return redirect(f"{reverse(redirect_url)}?tab=pending")


