from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.core.mail import send_mail
from django.views.generic import TemplateView
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from pages.forms import AdminResponseForm, ContactForm
from accounts.models import CustomUser
from events.models import Event
from resources.models import Corpus, NLPTool ,Document , Course
from projects.models import Project ,ProjectMember
from django.contrib.auth import get_user_model
from forum.models import Topic , ChatRoom, Message
from django.db.models.functions import TruncDate, TruncMonth
from notifications.models import Notification
from QA.models import Post , Question
from django.db.models import Count, Sum
import datetime
import json
from datetime import timedelta
from django.utils import timezone
from django.core.paginator import Paginator

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
        context['projects_count'] = Project.objects.count()
        context['members_count'] = User.objects.count()
        
        # Posts populaires (les plus likés)
        context['popular_posts'] = Post.objects.annotate(
            total_likes=Count('likes')
        ).order_by('-total_likes', '-created_at')[:3]



        # Ressources les plus vues
        # Récupérer les ressources de chaque type, les combiner et les trier
        most_viewed_resources = []

        # Récupérer les 5 corpus les plus vus
        most_viewed_corpus = Corpus.objects.order_by('-views_count')[:3]
        for resource in most_viewed_corpus:
             resource.resource_type_display = "Corpus"
             most_viewed_resources.append(resource)

        # Récupérer les 5 outils NLP les plus vus
        most_viewed_tools = NLPTool.objects.order_by('-views_count')[:3]
        for resource in most_viewed_tools:
             resource.resource_type_display = "Tool"
             most_viewed_resources.append(resource)

        # Récupérer les 5 documents les plus vus
        most_viewed_documents = Document.objects.order_by('-views_count')[:3]
        for resource in most_viewed_documents:
             resource.resource_type_display = resource.get_document_type_display()
             most_viewed_resources.append(resource)

        # Récupérer les 5 cours les plus vus
        most_viewed_courses = Course.objects.order_by('-views_count')[:3]
        for resource in most_viewed_courses:
             resource.resource_type_display = "Course"
             most_viewed_resources.append(resource)

        # Trier toutes les ressources les plus vues par nombre de vues (décroissant) et prendre les 5 premières au total
        context['most_viewed_resources'] = sorted(most_viewed_resources, key=lambda x: x.views_count, reverse=True)[:3]

      
            
        context['page'] = 'home'
        
        return context
    

# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q
from .models import  ContactMessage, Stats ,UserStatusHistory

from institutions.models import Institution

import datetime

from accounts.forms import CustomUserChangeForm  


User = get_user_model()

def is_admin(user):
    """Check if user is an admin"""
    return user.is_staff or user == 'admin'


@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    """Main admin dashboard view"""
    today = timezone.now().date()
    last_year = today - datetime.timedelta(days=365) # Pour les 12 derniers mois
    
    # Recent users
    recent_users = User.objects.filter(
        date_joined__gte=today-datetime.timedelta(days=30)
    ).order_by('-date_joined')[:10]
    
    # Recent content
    recent_publications =  Document.objects.order_by('-creation_date').prefetch_related('authors')[:5]
    recent_corpora = Corpus.objects.all().order_by('-creation_date')[:5]
    recent_tools = NLPTool.objects.all().order_by('-creation_date')[:5]
    recent_projects = Project.objects.all().order_by('-created_at')[:5]
    
    # Count statistics
    users_count = User.objects.count()
    resources_count = (
        Document.objects.count() + 
        Corpus.objects.count() + 
        NLPTool.objects.count() + 
        Course.objects.count()
    )
    projects_count = Project.objects.filter(status='ongoing').count()
    forum_posts_count = Topic.objects.count() + ChatRoom.objects.count()
    
    # Nouveaux compteurs pour la répartition des ressources
    publications_count = Document.objects.count()
    corpora_count = Corpus.objects.count()
    tools_count = NLPTool.objects.count()
    courses_count = Course.objects.count()
    
    # Compteurs pour les statuts des projets
    projects_in_progress = Project.objects.filter(status='ongoing').count()
    projects_completed = Project.objects.filter(status='completed').count()
    projects_pending = Project.objects.filter(status='pending').count()
    projects_cancelled = Project.objects.filter(status='cancelled').count()
    
    # Données pour l'activité du forum
    forum_topics_data = []
    forum_messages_data = []
    
    # Récupérer les données du forum pour les 12 derniers mois
    for i in range(12):
        month = today - datetime.timedelta(days=30 * i)
        month_start = month.replace(day=1)
        if i == 0:
            month_end = today
        else:
            next_month = month.replace(day=28) + datetime.timedelta(days=4)
            month_end = next_month - datetime.timedelta(days=next_month.day)
        
        # Comptage des nouveaux sujets
        topics_count = Topic.objects.filter(
            created_at__gte=month_start,
            created_at__lte=month_end
        ).count()
        
        # Comptage des nouveaux messages
        messages_count = ChatRoom.objects.filter(
            created_at__gte=month_start,
            created_at__lte=month_end
        ).count()
        
        forum_topics_data.append(topics_count)
        forum_messages_data.append(messages_count)
    
    # Inverser les listes pour avoir l'ordre chronologique
    forum_topics_data.reverse()
    forum_messages_data.reverse()
    
    # Users by type
    users_by_type = User.objects.order_by('-date_joined')[:10]
    
    # Get monthly growth rates
    last_month = today - datetime.timedelta(days=30)
    two_months_ago = today - datetime.timedelta(days=60)
    
    users_this_month = User.objects.filter(date_joined__gte=last_month).count()
    users_last_month = User.objects.filter(
        date_joined__gte=two_months_ago, 
        date_joined__lt=last_month
    ).count()
    
    if users_last_month > 0:
        user_growth = ((users_this_month - users_last_month) / users_last_month) * 100
    else:
        user_growth = 100 if users_this_month > 0 else 0
        
    # Publications this month
    pubs_this_month = Document.objects.filter(creation_date__gte=last_month).count()
    pubs_last_month = Document.objects.filter(
        creation_date__gte=two_months_ago, 
        creation_date__lt=last_month
    ).count()
    
    if pubs_last_month > 0:
        pubs_growth = ((pubs_this_month - pubs_last_month) / pubs_last_month) * 100
    else:
        pubs_growth = 100 if pubs_this_month > 0 else 0

    # Projects growth
    projects_this_month = Project.objects.filter(created_at__gte=last_month).count()
    projects_last_month = Project.objects.filter(
        created_at__gte=two_months_ago, 
        created_at__lt=last_month
    ).count()
    
    if projects_last_month > 0:
        projects_growth = ((projects_this_month - projects_last_month) / projects_last_month) * 100
    else:
        projects_growth = 100 if projects_this_month > 0 else 0
    
    # Forum posts growth
    posts_this_month = (
        Topic.objects.filter(created_at__gte=last_month).count() + 
        ChatRoom.objects.filter(created_at__gte=last_month).count()
    )
    
    posts_last_month = (
        Topic.objects.filter(created_at__gte=two_months_ago, created_at__lt=last_month).count() + 
        ChatRoom.objects.filter(created_at__gte=two_months_ago, created_at__lt=last_month).count()  
    )
    
    if posts_last_month > 0:
        posts_growth = ((posts_this_month - posts_last_month) / posts_last_month) * 100
    else:
        posts_growth = 100 if posts_this_month > 0 else 0
    
    # Données pour le graphique d'activité récente (nouveaux utilisateurs et ressources par mois)
    # Nouveaux utilisateurs par mois
    monthly_users = User.objects.filter(date_joined__date__gte=last_year).annotate(month=TruncMonth('date_joined')).values('month').annotate(count=Count('id')).order_by('month')

    # Nouvelles ressources (Publications, Corpus, Outils) par mois
    monthly_publications = Document.objects.filter(creation_date__date__gte=last_year).annotate(month=TruncMonth('creation_date')).values('month').annotate(count=Count('id')).order_by('month')

    monthly_corpora = Corpus.objects.filter(creation_date__date__gte=last_year).annotate(month=TruncMonth('creation_date')).values('month').annotate(count=Count('id')).order_by('month')


    monthly_tools = NLPTool.objects.filter(creation_date__date__gte=last_year).annotate(month=TruncMonth('creation_date')).values('month').annotate(count=Count('id')).order_by('month')


    # Combiner les données mensuelles des ressources
    # Créez un dictionnaire pour agréger les comptes par mois
    monthly_resources_dict = {}

    for item in monthly_publications:
        month_key = item['month'].strftime('%Y-%m')
        monthly_resources_dict[month_key] = monthly_resources_dict.get(month_key, 0) + item['count']

    for item in monthly_corpora:
        month_key = item['month'].strftime('%Y-%m')
        monthly_resources_dict[month_key] = monthly_resources_dict.get(month_key, 0) + item['count']
        
    for item in monthly_tools:
        month_key = item['month'].strftime('%Y-%m')
        monthly_resources_dict[month_key] = monthly_resources_dict.get(month_key, 0) + item['count']

    # Préparez les labels (mois) et les datasets pour le graphique
    # Assurez-vous d'avoir tous les mois des 12 derniers mois, même s'il n'y a pas de données
    all_months = []
    for i in range(12):
        month = today - datetime.timedelta(days=30 * i)
        all_months.append(month.strftime('%Y-%m'))
    all_months.reverse()

    chart_labels = [datetime.datetime.strptime(month, '%Y-%m').strftime('%b %Y') for month in all_months]
    users_activity_data = []
    resources_activity_data = []

    monthly_users_dict = {item['month'].strftime('%Y-%m'): item['count'] for item in monthly_users}

    for month in all_months:
        users_activity_data.append(monthly_users_dict.get(month, 0))
        resources_activity_data.append(monthly_resources_dict.get(month, 0))

    # Combine all statistics
    context = {
        'recent_users': recent_users,
        'recent_publications': recent_publications,
        'recent_corpora': recent_corpora,
        'recent_tools': recent_tools,
        'recent_projects': recent_projects,
        'users_count': users_count,
        'resources_count': resources_count,
        'projects_count': projects_count,
        'forum_posts_count': forum_posts_count,
        'users_by_type': users_by_type,
        'user_growth': user_growth,
        'pubs_growth': pubs_growth,
        'projects_growth': projects_growth,
        'posts_growth': posts_growth,
        'chart_labels': json.dumps(chart_labels),
        'users_activity_data': json.dumps(users_activity_data),
        'resources_activity_data': json.dumps(resources_activity_data),
        # Nouvelles données pour les graphiques
        'publications_count': publications_count,
        'corpora_count': corpora_count,
        'tools_count': tools_count,
        'courses_count': courses_count,
        'projects_in_progress': projects_in_progress,
        'projects_completed': projects_completed,
        'projects_pending': projects_pending,
        'projects_cancelled': projects_cancelled,
        'forum_topics_data': json.dumps(forum_topics_data),
        'forum_messages_data': json.dumps(forum_messages_data),
    }
    
    return render(request, 'admin/dashboard.html', context)


@login_required
@user_passes_test(is_admin)
def admin_users(request):
    """Admin user management view"""
    # Récupération des filtres passés en querystring
    filter_status = request.GET.get('status', '')
    search = request.GET.get('search', '').strip()
    
    # Base queryset : tous les utilisateurs
    qs = User.objects.all().order_by('-date_joined')
    
    # Filtrage "statut"
    if filter_status == 'active':
        qs = qs.filter(is_active=True , is_email_verified=True)
    elif filter_status == 'pending':
        # en attente : non actifs et non vérifiés
        qs = qs.filter(is_active=False , is_email_verified=True )
    elif filter_status == 'blocked':
        # bloqués : non actifs mais vérifiés (ou autre règle métier)
        qs = qs.filter(is_active=False, is_email_verified=True)
    
    # Recherche full-text sur username, email, prénom, nom
    if search:
        qs = qs.filter(
            Q(full_name__icontains=search) |
            Q(email__icontains=search) 
        )
    
    # Nombre d'utilisateurs "en attente" pour l'en-tête
    pending_users_count = User.objects.filter(
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
@login_required
@user_passes_test(is_admin)
def admin_users_new(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        status = request.POST.get('status', 'active')
       

        # 1. Vérification des mots de passe
        if password1 != password2:
            messages.error(request, "Les mots de passe ne correspondent pas.")
            return render(request, 'admin/users_new.html')

        # 2. Vérification de l’unicité de l’email
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, f"L'utilisateur avec l'email {email} existe déjà.")
            return render(request, 'admin/users_new.html')

        # 3. Récupération de l'institution (si fournie)
        institution_obj = None
        
        

        # 4. Création du compte admin
        user = CustomUser.objects.create_user(
            email=email,
            password=password1,
            full_name=full_name,
            institution=institution_obj,
        )

        user.status = status
        user.is_active = True         
        user.is_staff = True         
        user.is_superuser = True      
        user.save()

        messages.success(request, f"L'administrateur {full_name} a été créé avec succès.")
        return redirect('pages:admin_users')

    return render(request, 'admin/users_new.html')


@login_required
@user_passes_test(is_admin)
@transaction.atomic
def admin_user_delete(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)

    if user_obj == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect('pages:admin_users')

    if request.method == 'POST':
        # Historique
        UserStatusHistory.objects.create(
            user=user_obj,
            old_status=user_obj.status,
            new_status='deleted',
            changed_by=request.user,
            change_date=timezone.now(),
            reason='Account deleted by admin'
        )
        # Suppression
        user_obj.delete()

        messages.success(request, f"The user {user_obj.full_name} has been successfully deleted.")
        return redirect('pages:admin_users')

    return render(request, 'admin/users_delete_confirm.html', {'user_obj': user_obj})



@login_required
@user_passes_test(is_admin)
@transaction.atomic
def admin_user_activate(request, user_id):
    """Vue pour activer un utilisateur."""
    user = get_object_or_404(User, id=user_id)
    
    if user.status == 'active':
        messages.info(request, f"The user {user.full_name} is already active.")
        return redirect('pages:admin_users')
    
    old_status = user.status
    user.is_active = True
    user.status = 'active'
    user.is_verified = True
    user.save()
    
    # Créer une entrée dans l'historique
    UserStatusHistory.objects.create(
        user=user,
        old_status=old_status,
        new_status='active',
        changed_by=request.user,
        change_date=timezone.now()
    )
    
    # Notification d'activation
    Notification.objects.create(
        recipient=user,
        title="Account activated",
        message="Your account has been activated by an administrator. You can now access all features."
    )
    
    messages.success(request, f"The user {user.full_name} has been successfully activated.")
    
    # Rediriger vers la page précédente si disponible
    next_url = request.GET.get('next', reverse('pages:admin_users'))
    return redirect(next_url)

@login_required
@user_passes_test(is_admin)
def admin_user_block(request, user_id):
    """Vue pour bloquer un utilisateur."""
    user = get_object_or_404(User, id=user_id)
    
    # Empêcher le blocage de soi-même
    if user == request.user:
        messages.error(request, "You cannot block your own account.")
        return redirect('pages:admin_users')
    
    if user.status == 'blocked':
        messages.info(request, f"The user {user.full_name} is already blocked.")
        return redirect('pages:admin_users')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        old_status = user.status
        user.is_active = False
        user.status = 'blocked'
        user.save()
        
        # Créer une entrée dans l'historique
        UserStatusHistory.objects.create(
            user=user,
            old_status=old_status,
            new_status='blocked',
            changed_by=request.user,
            change_date=timezone.now(),
            reason=reason
        )
        
        # Notification de blocage
        Notification.objects.create(
            recipient=user,
            title="Blocked account",
            message="Your account has been locked by an administrator. Please contact support if necessary."
        )
        
        messages.success(request, f"The user {user.full_name} has been successfully blocked.")
        return redirect('pages:admin_users')
    
    return render(request, 'admin/block_confirm.html', {'user_obj': user})


@login_required
@user_passes_test(is_admin)
def admin_user_history(request, user_id):
    """Vue pour afficher l'historique des statuts d'un utilisateur."""
    user = get_object_or_404(User, id=user_id)
    
    # Récupérer les filtres
    status_filter = request.GET.get('status_filter', '')
    admin_filter = request.GET.get('admin_filter', '')
    period_filter = request.GET.get('period_filter', '')

    # Base queryset pour l'historique de l'utilisateur spécifique
    history_qs = UserStatusHistory.objects.filter(user=user).order_by('-change_date')

    # Appliquer les filtres
    if status_filter:
        history_qs = history_qs.filter(new_status=status_filter)
    if admin_filter:
        history_qs = history_qs.filter(changed_by__id=admin_filter)

    # Filtrage par période
    today = timezone.now().date()
    if period_filter == 'day':
        history_qs = history_qs.filter(change_date__date=today)
    elif period_filter == 'week':
        start_week = today - datetime.timedelta(days=today.weekday())
        history_qs = history_qs.filter(change_date__date__gte=start_week)
    elif period_filter == 'month':
        start_month = today.replace(day=1)
        history_qs = history_qs.filter(change_date__date__gte=start_month)

    # Statistiques pour les cartes
    total_changes = UserStatusHistory.objects.filter(user=user).count()
    activations = UserStatusHistory.objects.filter(user=user, new_status='active').count()
    blocks = UserStatusHistory.objects.filter(user=user, new_status='blocked').count()

    # Changements récents (par défaut, les 7 derniers jours)
    seven_days_ago = timezone.now() - datetime.timedelta(days=7)
    recent_changes_count = UserStatusHistory.objects.filter(user=user, change_date__gte=seven_days_ago).count()
    
    # Récupérer tous les administrateurs pour le filtre
    all_admins = User.objects.filter(is_staff=True).order_by('full_name')

    context = {
        'user_obj': user,
        'recent_history': history_qs, # Renommé history en recent_history
        'total_changes': total_changes,
        'activations': activations,
        'blocks': blocks,
        'recent_changes': recent_changes_count, # Utilise le compte des 7 derniers jours
        'status_filter': status_filter,
        'admin_filter': int(admin_filter) if admin_filter else '', # Convertir en int si non vide
        'period_filter': period_filter,
        'all_admins': all_admins,
    }

    return render(request, 'admin/history.html', context)

@login_required
@user_passes_test(is_admin)
def admin_user_edit(request, user_id):
    """Admin view to edit user details"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f"The user {user.username} has been successfully updated.")
            return redirect('pages:admin_users')
    else:
        form = CustomUserChangeForm(instance=user)
    
    context = {
        'form': form,
        'user': user,
    }
    
    return render(request, 'admin/user_edit.html', context)


@login_required
@user_passes_test(is_admin)
def admin_user_status(request, user_id, status):
    """Change user status (approve, block, etc.)"""
    user = get_object_or_404(User, id=user_id)
    
    # Enregistrer l'ancien statut pour l'historique
    old_status = user.status
    
    user.status = status
    
    user.save()
    
    # Enregistrer l'historique du changement de statut
    UserStatusHistory.objects.create(
        user=user,
        old_status=old_status,
        new_status=user.status,
        changed_by=request.user,
        #reason=user.block_reason # Enregistrer la raison dans l'historique aussi
    )
    
    status_messages = {
        'active': "activé",
        'pending': "mis en attente",
        'inactive': "désactivé",
        'blocked': "bloqué"
    }
    
    messages.success(request, f"The user{user.username} a été {status_messages.get(status, 'updated')}.")
    return redirect('pages:admin_users')


@login_required
@user_passes_test(is_admin)
def admin_publications(request):
    """Admin publications management"""
    # Filter parameters
    publication_type = request.GET.get('publication_type', '')
    search = request.GET.get('search', '')
    
    # Base queryset
    publications = Document.objects.all().order_by('-creation_date')
    
    # Apply filters
    if publication_type:
        publications = publications.filter(document_type=publication_type)
    if search:
        publications = publications.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search) |
            Q(keywords__icontains=search) |
            Q(authors__full_name__icontains=search)
        ).distinct()
    
    context = {
        'publications': publications,
        'filter_publication_type': publication_type,
        'search': search,
    }
    
    return render(request, 'admin/publications.html', context)


@login_required
@user_passes_test(is_admin)
def admin_corpora(request):
    """Admin corpora management"""
    # Filter parameters
    corpus_type = request.GET.get('corpus_type', '')
    search = request.GET.get('search', '')
    
    # Base queryset
    corpora = Corpus.objects.all().order_by('-creation_date')
    
    # Apply filters
    if corpus_type:
        corpora = corpora.filter(corpus_type=corpus_type)
    if search:
        corpora = corpora.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search) |
            Q(author__full_name__icontains=search)
        )
    
    context = {
        'corpora': corpora,
        'filter_corpus_type': corpus_type,
        'search': search,
    }
    
    return render(request, 'admin/corpora.html', context)

@login_required
@user_passes_test(is_admin)
def admin_tools(request):
    """Admin tools management"""
    # Filter parameters
    tool_type = request.GET.get('tool_type', '')
    search = request.GET.get('search', '')
    
    # Base queryset
    tools = NLPTool.objects.all().order_by('-creation_date')
    
    # Apply filters
    if tool_type:
        tools = tools.filter(tool_type=tool_type)
    if search:
        tools = tools.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search) |
            Q(author__full_name__icontains=search)
        )
    
    context = {
        'tools': tools,
        'filter_tool_type': tool_type,
        'search': search,
    }
    
    return render(request, 'admin/tools.html', context)


@login_required
@user_passes_test(is_admin)
def admin_projects(request):
    """Admin projects management"""
    # Filter parameters
    status = request.GET.get('status', '')
    visibility = request.GET.get('visibility', '')
    search = request.GET.get('search', '')
    
    # Base queryset
    projects = Project.objects.all().order_by('-created_at')
    
    # Apply filters
    if status:
        projects = projects.filter(status=status)
    if visibility:
        projects = projects.filter(visibility=visibility)
    if search:
        projects = projects.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search) |
            Q(status__icontains=search) 
        ).distinct()

    # Statistiques dynamiques
    total_count = projects.count()
    in_progress_count = projects.filter(status='ongoing').count()
    completed_count = projects.filter(status='completed').count()

    # Croissance du nombre de projets ce mois
    today = timezone.now().date()
    last_month = today - timedelta(days=30)
    two_months_ago = today - timedelta(days=60)
    projects_this_month = projects.filter(created_at__gte=last_month).count()
    projects_last_month = projects.filter(created_at__gte=two_months_ago, created_at__lt=last_month).count()
    if projects_last_month > 0:
        projects_growth = ((projects_this_month - projects_last_month) / projects_last_month) * 100
    else:
        projects_growth = 100 if projects_this_month > 0 else 0

    # Croissance du nombre de projets terminés ce mois
    completed_this_month = projects.filter(status='completed', created_at__gte=last_month).count()
    completed_last_month = projects.filter(status='completed', created_at__gte=two_months_ago, created_at__lt=last_month).count()
    if completed_last_month > 0:
        completed_growth = ((completed_this_month - completed_last_month) / completed_last_month) * 100
    else:
        completed_growth = 100 if completed_this_month > 0 else 0

    # Calcul de la durée moyenne des projets terminés sur les 30 derniers jours
    end_date_current = timezone.now().date()
    start_date_current = end_date_current - timedelta(days=30)
    completed_current_period = Project.objects.filter(status='completed', date_end__gte=start_date_current, date_end__lte=end_date_current)

    average_duration_current = timedelta(0)
    if completed_current_period.count() > 0:
        total_duration_current = sum([(p.date_end - p.date_start) for p in completed_current_period if p.date_start and p.date_end], timedelta(0))
        # Éviter la division par zéro si date_end == date_start pour tous les projets
        total_seconds_current = total_duration_current.total_seconds()
        if total_seconds_current > 0:
             average_duration_current = total_duration_current / completed_current_period.count()

    # Calcul de la durée moyenne des projets terminés sur les 30 jours précédents
    end_date_previous = start_date_current - timedelta(days=1)
    start_date_previous = end_date_previous - timedelta(days=30)
    completed_previous_period = Project.objects.filter(status='completed', date_end__gte=start_date_previous, date_end__lte=end_date_previous)

    average_duration_previous = timedelta(0)
    if completed_previous_period.count() > 0:
        total_duration_previous = sum([(p.date_end - p.date_start) for p in completed_previous_period if p.date_start and p.date_end], timedelta(0))
         # Éviter la division par zéro si date_end == date_start pour tous les projets
        total_seconds_previous = total_duration_previous.total_seconds()
        if total_seconds_previous > 0:
             average_duration_previous = total_duration_previous / completed_previous_period.count()

    # Calcul de la différence et de la tendance
    duration_difference = average_duration_current - average_duration_previous
    duration_difference_days = duration_difference.days

    if duration_difference_days > 0:
        duration_trend_text = f"+{duration_difference_days}j vs previous period"
        duration_trend_class = 'trend-down' # Durée plus longue = tendance négative
    elif duration_difference_days < 0:
        duration_trend_text = f"{duration_difference_days}jvs previous period"
        duration_trend_class = 'trend-up' # Durée plus courte = tendance positive
    else:
        duration_trend_text = "Stable"
        duration_trend_class = 'trend-neutral'

    # La durée moyenne affichée sera celle de la période actuelle
    average_duration_display_days = average_duration_current.days if average_duration_current else 0

    context = {
        'projects': projects,
        'filter_status': status,
        'filter_visibility': visibility,
        'search': search,
        'projects_growth': round(projects_growth, 2),
        'in_progress_count': in_progress_count,
        'completed_count': completed_count,
        'total_count': total_count,
        'completed_growth': round(completed_growth, 2),
        'average_duration_display_days': average_duration_display_days,
        'duration_trend_text': duration_trend_text,
        'duration_trend_class': duration_trend_class,
    }
    return render(request, 'admin/projects.html', context)


@login_required
@user_passes_test(is_admin)
def admin_courses(request):
    """Admin courses management"""
    # Filter parameters
    level = request.GET.get('level', '')
    is_public = request.GET.get('is_public', '')
    search = request.GET.get('search', '')
    
    # Base queryset
    courses = Course.objects.all().order_by('-creation_date')
    
    # Apply filters
    if level:
        courses = courses.filter(level=level)
    if is_public:
        courses = courses.filter(is_public=(is_public == 'true'))
    if search:
        courses = courses.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search) |
            Q(author__full_name__icontains=search)
        )
    
    # Statistiques dynamiques pour les cours
    total_courses_count = courses.count()

    # Nombre de cours créés ce mois (derniers 30 jours)
    today = timezone.now().date()
    last_month = today - timedelta(days=30)
    two_months_ago = today - timedelta(days=60)
    courses_this_month_count = Course.objects.filter(creation_date__gte=last_month).count()
    courses_last_month_count = Course.objects.filter(creation_date__gte=two_months_ago, creation_date__lt=last_month).count()

    # Calcul de la croissance par rapport au mois dernier
    if courses_last_month_count > 0:
        courses_growth = ((courses_this_month_count - courses_last_month_count) / courses_last_month_count) * 100
    else:
        courses_growth = 100 if courses_this_month_count > 0 else 0

    # Déterminer la classe CSS pour la tendance
    if courses_growth > 0:
        courses_growth_class = 'trend-up'
    elif courses_growth < 0:
        courses_growth_class = 'trend-down'
    else:
        courses_growth_class = 'trend-neutral'

    context = {
        'courses': courses,
        'filter_level': level,
        'filter_is_public': is_public,
        'search': search,
        'total_courses_count': total_courses_count,
        'courses_this_month_count': courses_this_month_count,
        'courses_growth': round(courses_growth, 2),
        'courses_growth_class': courses_growth_class,
    }
    
    return render(request, 'admin/courses.html', context)


@login_required
@user_passes_test(is_admin)
def admin_forum(request):
    """Admin forum management"""
    # Filter parameters
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    page_number = request.GET.get('page')

    # Base queryset with proper prefetch for chatrooms
    topics = Topic.objects.prefetch_related('chatrooms').annotate(
        total_messages=Count('chatrooms__messages')
    ).order_by('-created_at')

    # Apply filters
    if status == 'open':
        topics = topics.filter(is_closed=False)
    elif status == 'closed':
        topics = topics.filter(is_closed=True)

    if search:
        topics = topics.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search) |
            Q(creator__full_name__icontains=search)
        )

    # Pagination
    paginator = Paginator(topics, 10)
    page_obj = paginator.get_page(page_number)

    # Statistics
    total_topics_count = Topic.objects.count()
    open_topics_count = Topic.objects.filter(is_closed=False).count()
    closed_topics_count = Topic.objects.filter(is_closed=True).count()
    total_messages_count = Message.objects.count()

    context = {
        'topics': page_obj,
        'total_topics_count': total_topics_count,
        'open_topics_count': open_topics_count,
        'closed_topics_count': closed_topics_count,
        'total_messages_count': total_messages_count,
        'filter_status': status,
        'search': search,
    }

    return render(request, 'admin/forum.html', context)


# Add these additional views for proper topic management
@login_required
@user_passes_test(is_admin)
def admin_topic_detail(request, pk):
    """View topic details"""
    topic = get_object_or_404(Topic, pk=pk)
    return render(request, 'admin/topic_detail.html', {'topic': topic})


@login_required
@user_passes_test(is_admin)
def admin_topic_edit(request, pk):
    """Edit topic"""
    topic = get_object_or_404(Topic, pk=pk)
    if request.method == 'POST':
        # Handle topic update logic here
        pass
    return render(request, 'admin/topic_edit.html', {'topic': topic})


@login_required
@user_passes_test(is_admin)
def admin_topic_delete(request, pk):
    """Delete topic"""
    topic = get_object_or_404(Topic, pk=pk)
    if request.method == 'POST':
        topic.delete()
        return JsonResponse({'status': 'success'})
    return render(request, 'admin/topic_delete.html', {'topic': topic})


@login_required
@user_passes_test(is_admin)  
def admin_topic_toggle_status(request, pk):
    """Toggle topic status (open/closed)"""
    if request.method == 'POST':
        topic = get_object_or_404(Topic, pk=pk)
        topic.is_closed = not topic.is_closed
        topic.save()
        
        return JsonResponse({
            'status': 'success',
            'is_closed': topic.is_closed,
            'message': f'Topic {"fermé" if topic.is_closed else "ouvert"} avec succès'
        })
    
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'})


# Make sure you have this utility function
def is_admin(user):
    """Check if user is admin"""
    return user.is_staff or user.is_superuser or hasattr(user, 'is_admin') and user.is_admin
@login_required
@user_passes_test(is_admin)
def admin_institutions(request):
    """Admin institutions management"""
    # Filter parameters
    country = request.GET.get('country', '')
    is_active = request.GET.get('is_active', '')
    search = request.GET.get('search', '')
    
    # Base queryset
    institutions = Institution.objects.all().order_by('name')
    
    # Apply filters
    if country:
        institutions = institutions.filter(country=country)
    if is_active:
        institutions = institutions.filter(is_active=(is_active == 'true'))
    if search:
        institutions = institutions.filter(
            Q(name__icontains=search) | 
            Q(acronym__icontains=search) |
            Q(description__icontains=search)
        )
    
    # Get unique countries for filter
    countries = Institution.objects.values_list('country', flat=True).distinct()
    
    context = {
        'institutions': institutions,
        'countries': countries,
        'filter_country': country,
        'filter_is_active': is_active,
        'search': search,
    }
    
    return render(request, 'admin/institutions.html', context)


@login_required
@user_passes_test(is_admin)
def admin_calls(request):
    """Admin calls for papers management"""
    # Filter parameters
    call_type = request.GET.get('call_type', '')
    is_active = request.GET.get('is_active', '')
    is_approved = request.GET.get('is_approved', '')
    search = request.GET.get('search', '')
    
    # Base queryset
    calls = Event.objects.all().order_by('-created_at')
    
    # Apply filters
    if call_type:
       calls = calls.filter(event_type=call_type)
    if is_active:
        calls = calls.filter(is_active=(is_active == 'true'))
    if is_approved:
        calls = calls.filter(is_approved=(is_approved == 'true'))
    if search:
        calls = calls.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search) |
            Q(organizer__name__icontains=search) |
            Q(domains__icontains=search)
        )
    
    context = {
        'calls': calls,
        'filter_call_type': call_type,
        'filter_is_active': is_active,
        'filter_is_approved': is_approved,
        'search': search,
    }
    
    return render(request, 'admin/calls.html', context)

@login_required
@user_passes_test(is_admin)
def admin_statistics(request):
    """Admin statistics view"""
    # 1. Récupérer la plage de dates
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

    # 2. Charger les Stats existantes
    stats = Stats.objects.filter(date__gte=start_date, date__lte=end_date).order_by('date')

    # 3. Calculer les statistiques actuelles et les taux de croissance
    today = timezone.now().date()
    last_month = today - datetime.timedelta(days=30)
    two_months_ago = today - datetime.timedelta(days=60)

    # Statistiques actuelles
    # Récupérer les statistiques agrégées du modèle Stats pour la période actuelle
    stats_current_period = Stats.objects.filter(date__gte=start_date, date__lte=end_date)
    current_visits_count = stats_current_period.aggregate(total_visits=Sum('visits_count'))['total_visits'] or 0

    # Récupérer les statistiques agrégées du modèle Stats pour la période précédente
    # Pour simplifier, on prend la période de 30 jours avant le début de la période actuelle
    start_date_prev = start_date - datetime.timedelta(days=30)
    end_date_prev = start_date - datetime.timedelta(days=1)
    stats_previous_period = Stats.objects.filter(date__gte=start_date_prev, date__lte=end_date_prev)
    previous_visits_count = stats_previous_period.aggregate(total_visits=Sum('visits_count'))['total_visits'] or 0


    current_stats = {
        'users_count': User.objects.count(),
        'publications_count': Document.objects.count(),
        'corpora_count': Corpus.objects.count(),
        'tools_count': NLPTool.objects.count(),
        'projects_count': Project.objects.count(),
        'forum_posts_count': Topic.objects.count() + ChatRoom.objects.count(),
        'visits_count': current_visits_count, # Utilise les vues agrégées du modèle Stats
        'active_projects_count': Project.objects.filter(status='ongoing').count()
    }

    # Calcul des taux de croissance
    # Utilisateurs
    users_this_month = User.objects.filter(date_joined__gte=last_month).count()
    users_last_month = User.objects.filter(
        date_joined__gte=two_months_ago, 
        date_joined__lt=last_month
    ).count()
    current_stats['users_growth'] = ((users_this_month - users_last_month) / users_last_month * 100) if users_last_month > 0 else 100 if users_this_month > 0 else 0

    # Ressources
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
    current_stats['resources_growth'] = ((resources_this_month - resources_last_month) / resources_last_month * 100) if resources_last_month > 0 else 100 if resources_this_month > 0 else 0

    # Visites
    current_stats['visits_growth'] = ((current_visits_count - previous_visits_count) / previous_visits_count * 100) if previous_visits_count > 0 else 100 if current_visits_count > 0 else 0

    # Projets
    projects_this_month = Project.objects.filter(created_at__gte=last_month).count()
    projects_last_month = Project.objects.filter(
        created_at__gte=two_months_ago, 
        created_at__lt=last_month
    ).count()
    current_stats['projects_growth'] = ((projects_this_month - projects_last_month) / projects_last_month * 100) if projects_last_month > 0 else 100 if projects_this_month > 0 else 0

    # Forum
    forum_this_month = (
        Topic.objects.filter(created_at__gte=last_month).count() + 
        ChatRoom.objects.filter(created_at__gte=last_month).count()
    )
    forum_last_month = (
        Topic.objects.filter(created_at__gte=two_months_ago, created_at__lt=last_month).count() + 
        ChatRoom.objects.filter(created_at__gte=two_months_ago, created_at__lt=last_month).count()
    )
    current_stats['forum_growth'] = ((forum_this_month - forum_last_month) / forum_last_month * 100) if forum_last_month > 0 else 100 if forum_this_month > 0 else 0

    # 4. Préparer les données brutes pour les graphiques
    chart_dates = [stat.date.strftime('%Y-%m-%d') for stat in stats] # Formatte les dates en chaîne
    users_data = [stat.users_count for stat in stats]
    resources_data = [stat.publications_count + stat.corpora_count + stat.tools_count for stat in stats]
    visits_data = [stat.visits_count for stat in stats]

    # 5. Comptage des inscriptions utilisateurs par jour
    user_regs = (
        User.objects
        .filter(date_joined__date__gte=start_date, date_joined__date__lte=end_date)
        .annotate(day=TruncDate('date_joined'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    user_reg_dates = [row['day'].strftime('%Y-%m-%d') for row in user_regs] # Formatte les dates en chaîne
    user_reg_counts = [row['count'] for row in user_regs]

    # 6. Top 5 des ressources les plus vues
    top_resources = []
    
    # Publications
    top_publications = Document.objects.order_by('-views_count')[:2]
    for pub in top_publications:
        top_resources.append({
            'title': pub.title,
            'views': pub.views_count
        })
    
    # Corpus
    top_corpora = Corpus.objects.order_by('-views_count')[:2]
    for corpus in top_corpora:
        top_resources.append({
            'title': corpus.title,  
            'views': corpus.views_count
        })
    
    # Outils
    top_tools = NLPTool.objects.order_by('-views_count')[:1]
    for tool in top_tools:
        top_resources.append({
            'title': tool.title,  
            'views': tool.views_count
        })

    # Trier par nombre de vues
    top_resources.sort(key=lambda x: x['views'], reverse=True)
    top_resources = top_resources[:5]

    context = {
        'stats': stats,
        'current_stats': current_stats,
        'start_date': start_date,
        'end_date': end_date,
        'chart_dates': json.dumps(chart_dates),  # Sérialisation en JSON
        'users_data': json.dumps(users_data),  # Sérialisation en JSON
        'resources_data': json.dumps(resources_data),  # Sérialisation en JSON
        'visits_data': json.dumps(visits_data),  # Sérialisation en JSON
        'user_reg_dates': json.dumps(user_reg_dates),  # Sérialisation en JSON
        'user_reg_counts': json.dumps(user_reg_counts),  # Sérialisation en JSON
        'top_resources': top_resources,
    }

    return render(request, 'admin/statistics.html', context)

@login_required
@user_passes_test(is_admin)
def admin_settings(request):
    """Admin settings view"""
    # You can implement site settings model if needed
    return render(request, 'admin/settings.html')


@login_required
@user_passes_test(is_admin)
def admin_security(request):
    """Admin security view"""
    # Recent login attempts
    # Implement login attempts model if needed
    return render(request, 'admin/security.html')


# API endpoints for dashboard
@login_required
@user_passes_test(is_admin)
def admin_api_stats(request):
    """API endpoint for dashboard statistics"""
    today = timezone.now().date()
    last_month = today - datetime.timedelta(days=30)
    two_months_ago = today - datetime.timedelta(days=60)
    
    # Users stats
    users_count = User.objects.count()
    users_this_month = User.objects.filter(date_joined__gte=last_month).count()
    users_last_month = User.objects.filter(
        date_joined__gte=two_months_ago, 
        date_joined__lt=last_month
    ).count()
    
    if users_last_month > 0:
        user_growth = ((users_this_month - users_last_month) / users_last_month) * 100
    else:
        user_growth = 100 if users_this_month > 0 else 0
    
    # Combine all resources
    resources_count = (
        Document.objects.count() + 
        Corpus.objects.count() + 
        NLPTool.objects.count() + 
        Course.objects.count()
    )
    
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
    
    if resources_last_month > 0:
        resources_growth = ((resources_this_month - resources_last_month) / resources_last_month) * 100
    else:
        resources_growth = 100 if resources_this_month > 0 else 0
    
    # Projects
    projects_count = Project.objects.filter(status='ongoing').count()
    projects_this_month = Project.objects.filter(created_at__gte=last_month).count()
    projects_last_month = Project.objects.filter(
        created_at__gte=two_months_ago, 
        created_at__lt=last_month
    ).count()
    
    if projects_last_month > 0:
        projects_growth = ((projects_this_month - projects_last_month) / projects_last_month) * 100
    else:
        projects_growth = 100 if projects_this_month > 0 else 0
    
    # Forum posts
    forum_posts_count = Topic.objects.count() + ChatRoom.objects.count()
    posts_this_month = (
        Topic.objects.filter(created_at__gte=last_month).count() + 
        ChatRoom.objects.filter(created_at__gte=last_month).count()
    )
    
    posts_last_month = (
        Topic.objects.filter(created_at__gte=two_months_ago, created_at__lt=last_month).count() + 
        ChatRoom.objects.filter(created_at__gte=two_months_ago, created_at__lt=last_month).count()  
    )
    
    if posts_last_month > 0:
        posts_growth = ((posts_this_month - posts_last_month) / posts_last_month) * 100
    else:
        posts_growth = 100 if posts_this_month > 0 else 0
    
    return JsonResponse({
        'users': {
            'count': users_count,
            'growth': user_growth,
        },
        'resources': {
            'count': resources_count,
            'growth': resources_growth,
        },
        'projects': {
            'count': projects_count,
            'growth': projects_growth,
        },
        'forum_posts': {
            'count': forum_posts_count,
            'growth': posts_growth,
        },
    })


@login_required
@user_passes_test(is_admin)
def admin_api_recent_users(request):
    """API endpoint for recent users"""
    recent_users = User.objects.all().order_by('-date_joined')[:10]
    data = []
    
    for user in recent_users:
        data.append({
            'id': user.id,
            'username': user.username,
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
        items = Document.objects.all().order_by('-created_at')[:10]
        data = [
            {
                'id': item.id,
                'title': item.title,
                'type': item.get_publication_type_display(),
                'author': ", ".join([author.get_full_name() for author in item.authors.all()]),
                'date': item.created_at.strftime('%Y-%m-%d'),
                'status': item.get_status_display(),
            } 
            for item in items
        ]
    elif content_type == 'corpus':
        items = Corpus.objects.all().order_by('-created_at')[:10]
        data = [
            {
                'id': item.id,
                'title': item.name,
                'type': item.get_corpus_type_display(),
                'author': item.owner.get_full_name(),
                'date': item.created_at.strftime('%Y-%m-%d'),
                'status': item.get_status_display(),
            } 
            for item in items
        ]
    elif content_type == 'tools':
        items = NLPTool.objects.all().order_by('-created_at')[:10]
        data = [
            {
                'id': item.id,
                'title': item.name,
                'type': item.get_tool_type_display(),
                'author': item.owner.get_full_name(),
                'date': item.created_at.strftime('%Y-%m-%d'),
                'status': item.get_status_display(),
            } 
            for item in items
        ]
    elif content_type == 'projects':
        items = ProjectMember.objects.all().order_by('-created_at')[:10]
        data = [
            {
                'id': item.id,
                'title': item.title,
                'type': 'Projet',
                'author': ", ".join([participant.get_full_name() for participant in item.participants.all()[:2]]),
                'date': item.created_at.strftime('%Y-%m-%d'),
                'status': item.get_status_display(),
            } 
            for item in items
        ]
    else:
        # All content mixed
        publications = Document.objects.all().order_by('-created_at')[:5]
        corpora = Corpus.objects.all().order_by('-created_at')[:5]
        tools = NLPTool.objects.all().order_by('-created_at')[:5]
        
        data = []
        
        for item in publications:
            data.append({
                'id': item.id,
                'title': item.title,
                'type': 'Publication',
                'author': ", ".join([author.get_full_name() for author in item.authors.all()]),
                'date': item.created_at.strftime('%Y-%m-%d'),
                'status': item.get_status_display(),
            })
        
        for item in corpora:
            data.append({
                'id': item.id,
                'title': item.name,
                'type': 'Corpus',
                'author': item.owner.get_full_name(),
                'date': item.created_at.strftime('%Y-%m-%d'),
                'status': item.get_status_display(),
            })
        
        for item in tools:
            data.append({
                'id': item.id,
                'title': item.name,
                'type': 'Outil',
                'author': item.owner.get_full_name(),
                'date': item.created_at.strftime('%Y-%m-%d'),
                'status': item.get_status_display(),
            })
        
        # Sort by date
        data.sort(key=lambda x: x['date'], reverse=True)
        data = data[:10]
    
    return JsonResponse({'content': data})

def contact_view(request):
    """Vue pour le formulaire de contact public"""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            contact_message = form.save(commit=False)
            if request.user.is_authenticated:
                contact_message.user = request.user
            contact_message.save()
            
            # Envoyer une notification email à l'admin (optionnel)
            try:
                send_mail(
                    subject=f"[Arabic NLP Platform] New Contact Message: {contact_message.get_subject_display()}",
                    message=f"New message from {contact_message.name} ({contact_message.email})\n\n{contact_message.message}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.ADMIN_EMAIL],  # Vous devez définir cette variable dans settings.py
                    fail_silently=True,
                )
            except:
                pass
            
            messages.success(request, _('Your message has been sent successfully. We will get back to you soon.'))
            return redirect('contact:contact')
    else:
        form = ContactForm()
        # Préremplir les champs pour les utilisateurs connectés
        if request.user.is_authenticated:
            form.initial['name'] = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
            form.initial['email'] = request.user.email
    
    return render(request, 'contact/contact.html', {
        'form': form,
        'page': 'contact'
    })

@login_required
def admin_contact_list(request):
    """Vue pour lister les messages de contact dans l'admin"""
    if not request.user.is_staff:
        messages.error(request, _('You do not have permission to access this page.'))
        return redirect('pages:home')
    
    # Filtres
    status_filter = request.GET.get('status', '')
    subject_filter = request.GET.get('subject', '')
    search_query = request.GET.get('search', '')
    
    # Queryset de base
    messages_list = ContactMessage.objects.all()
    
    # Appliquer les filtres
    if status_filter:
        messages_list = messages_list.filter(status=status_filter)
    if subject_filter:
        messages_list = messages_list.filter(subject=subject_filter)
    if search_query:
        messages_list = messages_list.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(message__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(messages_list, 20)
    page_number = request.GET.get('page')
    messages_page = paginator.get_page(page_number)
    
    # Statistiques
    stats = {
        'total': ContactMessage.objects.count(),
        'pending': ContactMessage.objects.filter(status='pending').count(),
        'read': ContactMessage.objects.filter(status='read').count(),
        'replied': ContactMessage.objects.filter(status='replied').count(),
        'closed': ContactMessage.objects.filter(status='closed').count(),
    }
    
    context = {
        'messages': messages_page,
        'stats': stats,
        'status_filter': status_filter,
        'subject_filter': subject_filter,
        'search_query': search_query,
        'status_choices': ContactMessage.STATUS_CHOICES,
        'subject_choices': ContactMessage.SUBJECT_CHOICES,
    }
    
    return render(request, 'admin/contact_list.html', context)

@login_required
def admin_contact_detail(request, pk):
    """Vue pour voir et répondre à un message de contact"""
    if not request.user.is_staff:
        messages.error(request, _('You do not have permission to access this page.'))
        return redirect('pages:home')
    
    contact_message = get_object_or_404(ContactMessage, pk=pk)
    
    # Marquer comme lu si c'est la première fois
    if contact_message.status == 'pending':
        contact_message.status = 'read'
        contact_message.save()
    
    if request.method == 'POST':
        form = AdminResponseForm(request.POST, instance=contact_message)
        if form.is_valid():
            response = form.save(commit=False)
            response.responded_by = request.user
            response.responded_at = timezone.now()
            if response.admin_response and response.status != 'replied':
                response.status = 'replied'
            response.save()
            
            # Envoyer la réponse par email si il y a une réponse
            if response.admin_response:
                try:
                    send_mail(
                        subject=f"[Arabic NLP Platform] Response to your message: {contact_message.get_subject_display()}",
                        message=f"Hello {contact_message.name},\n\n{response.admin_response}\n\nBest regards,\nArabic NLP Platform Team",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[contact_message.email],
                        fail_silently=True,
                    )
                    messages.success(request, _('Response sent successfully.'))
                except:
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