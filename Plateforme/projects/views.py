from django.utils import timezone
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from .models import Project, ProjectMember
from django.db.models import Q
from django.db.models import Exists, OuterRef
from django.urls import reverse_lazy
from .forms import ProjectForm  
from django.contrib.auth import get_user_model
from notifications.models import Notification
from django.contrib import messages
from notifications.services import NotificationService
from accounts.views import LoginAndVerifiedRequiredMixin
from django.utils.translation import gettext_lazy as _


class ProjectListView(LoginAndVerifiedRequiredMixin, ListView):
    model = Project
    template_name = 'project_list.html'
    context_object_name = 'projects'
    
    def get_queryset(self):
        qs = super().get_queryset()
        
        membership = ProjectMember.objects.filter(
            project=OuterRef('pk'),
            member=self.request.user
        )
        
        # Filtrer les projets créés par l'utilisateur si le paramètre my_projects est présent
        if self.request.GET.get('my_projects'):
            qs = qs.filter(coordinator=self.request.user)
            
        # Ajouter le filtre par statut
        status_filter = self.request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
            
        # Ajouter la recherche
        search_query = self.request.GET.get('search')
        if search_query:
            qs = qs.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(institution__name__icontains=search_query) |
                Q(coordinator__full_name__icontains=search_query)
            )
            
        return qs.annotate(is_member=Exists(membership))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .models import Project # Importer ici pour éviter les problèmes de dépendance circulaire si Project utilise cette vue
        context['project_statuses'] = Project.STATUS_CHOICES

        context['page'] = 'research_projects'
        return context


class ProjectDetailView(LoginAndVerifiedRequiredMixin, DetailView):
    model = Project
    template_name = 'project_detail.html'
    context_object_name = 'project'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.get_object()
        
        # Récupérer les membres de l'équipe (exclure les rejetés)
        team_members = project.members.filter(
            status='accepted'
        ).select_related('member')
        
        # Récupérer les demandes en attente
        pending_requests = project.members.filter(
            status='pending'
        ).select_related('member')
        
        # Récupérer les demandes de départ en attente
        leave_requests = project.members.filter(
            status='accepted',
            leave_request_status='pending'
        ).select_related('member')
        
        # Vérifier le statut du membre actuel
        current_member = project.members.filter(
            member=self.request.user,
            status='accepted'
        ).first()
        
        context.update({
            'team_members': [pm.member for pm in team_members],
            'pending_requests': pending_requests,
            'leave_requests': leave_requests,
            'is_coordinator': project.coordinator == self.request.user,
            'is_member': current_member is not None,
            'has_pending_request': project.members.filter(
                member=self.request.user,
                status='pending'
            ).exists(),
            'has_pending_leave_request': current_member and current_member.leave_request_status == 'pending' if current_member else False,
            'leave_request_rejected': current_member and current_member.leave_request_status == 'rejected' if current_member else False
        })
        context['page'] = 'research_projects'
        return context



class ProjectCreateView(LoginAndVerifiedRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm  # Utilisez votre formulaire au lieu de fields
    template_name = 'project_new.html'
    success_url = reverse_lazy('projects:project_list')

    def form_valid(self, form):
        form.instance.coordinator = self.request.user
        response = super().form_valid(form)
        # NOTIFICATION à tous les utilisateurs actifs via le service
        User = get_user_model()
        for user in User.objects.filter(is_active=True):
            NotificationService.create_notification(
                recipient=user,
                notification_type='SYSTEM', # Ou un type spécifique si tu en crées un pour les nouveaux projets
                title="New research project",
                message=f"The project « {form.instance.title} » has just been published."
            )
           
        return response
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'research_projects'  
        return context


class ProjectUpdateView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, UpdateView):  
    model = Project
    form_class = ProjectForm  
    template_name = 'project_update.html'
    success_url = reverse_lazy('projects:project_list')
    
    def test_func(self):
        obj = self.get_object()
        return (
        self.request.user.is_staff
        or self.request.user.is_superuser
        or obj.coordinator == self.request.user
    )
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'research_projects'  
        return context
      


class ProjectDeleteView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Project
    template_name = 'project_delete.html'
    success_url = reverse_lazy('projects:project_list')

    def test_func(self):
        obj = self.get_object()
        return (
        self.request.user.is_staff
        or self.request.user.is_superuser
        or obj.coordinator == self.request.user
    )
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'research_projects'  
        return context


class JoinProjectView(LoginAndVerifiedRequiredMixin, View):
    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        
        # Vérifier si le projet est terminé
        if project.status == 'completed':
            messages.error(request, "This project is closed and is no longer accepting new members..")
            return redirect('projects:project_detail', pk=pk)

        # Vérifie si l'utilisateur n'est pas déjà membre
        if not ProjectMember.objects.filter(project=project, member=request.user).exists():
            # Créer une demande en attente
            ProjectMember.objects.create(
                project=project,
                member=request.user,
                role='member',
                status='pending'
            )
            # Notification au coordinateur du projet via le service
            NotificationService.create_membership_request(
                recipient=project.coordinator,
                project=project,
                sender=request.user
            )
            messages.success(request, "Your membership request has been sent to the project coordinator.")
        return redirect('projects:project_detail', pk=pk)


class AcceptMemberView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        project = get_object_or_404(Project, pk=self.kwargs['pk'])
        return self.request.user == project.coordinator

    def post(self, request, pk, member_id):
        project = get_object_or_404(Project, pk=pk)
        member = get_object_or_404(ProjectMember, project=project, member_id=member_id)
        
        if member.status == 'pending':
            member.status = 'accepted'
            member.save()
            
            # Notification au membre accepté via le service
            NotificationService.create_notification(
                recipient=member.member,
                notification_type='SYSTEM', # Ou un type spécifique
                title="Membership application accepted",
                message=f"Your request to join the project « {project.title} » was accepted."
            )
            messages.success(request, f"{member.member.full_name} was accepted into the project.")
        
        return redirect('projects:project_members', pk=pk)


class RejectMemberView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        project = get_object_or_404(Project, pk=self.kwargs['pk'])
        return self.request.user == project.coordinator

    def post(self, request, pk, member_id):
        project = get_object_or_404(Project, pk=pk)
        member = get_object_or_404(ProjectMember, project=project, member_id=member_id)
        
        if member.status == 'pending':
            member.status = 'rejected'
            member.save()
            
            # Notification au membre refusé via le service
            NotificationService.create_notification(
                recipient=member.member,
                notification_type='SYSTEM', # Ou un type spécifique
                title="Membership application refused",
                message=f"Your request to join the project « {project.title} » was refused."
            )
            messages.success(request, f"The request for {member.member.full_name} was refused.")
        
        return redirect('projects:project_members', pk=pk)


class ProjectMembersView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, DetailView):
    model = Project
    template_name = 'project_members.html'
    context_object_name = 'project'
    
    def test_func(self):
        project = self.get_object()
        return self.request.user == project.coordinator
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        context['pending_members'] = project.members.filter(status='pending')
        context['accepted_members'] = project.members.filter(status='accepted')
        context['rejected_members'] = project.members.filter(status='rejected')
        context['leave_requests'] = project.members.filter(
            status='accepted',
            leave_request_status='pending'
        )
        context['page'] = 'research_projects'
        return context


# Modification de la vue LeaveProjectView
class LeaveProjectView(LoginAndVerifiedRequiredMixin, View):
    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        
        # Trouver le membre
        member = ProjectMember.objects.filter(
            project=project, 
            member=request.user, 
            status='accepted'
        ).first()
        
        if member:
            # Vérifier s'il n'y a pas déjà une demande de départ en attente
            if member.leave_request_status == 'pending':
                messages.warning(request, _('You already have a pending leave request for this project.'))
                return redirect('projects:project_detail', pk=pk)
            
            # Marquer la demande de départ comme en attente
            member.leave_request_status = 'pending'
            member.leave_request_date = timezone.now()
            member.save()
            
            # Notification au coordinateur
            NotificationService.create_notification(
                recipient=project.coordinator,
                notification_type='LEAVE_REQUEST',
                title=_('Leave request'),
                message=_('{} wants to leave your project « {} ».').format(
                    request.user.full_name, 
                    project.title
                ),
                related_object=project,
                project_id=project.id,
                sender_id=request.user.id
            )
            
            messages.success(request, _('Your leave request has been sent to the project coordinator.'))
        else:
            messages.error(request, _('You are not a member of this project.'))
            
        return redirect('projects:project_detail', pk=pk)


# Nouvelle vue pour approuver/refuser les demandes de départ
class RespondToLeaveRequestView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        project = get_object_or_404(Project, pk=self.kwargs['pk'])
        return project.coordinator == self.request.user

    def post(self, request, pk, member_id):
        project = get_object_or_404(Project, pk=pk)
        member = get_object_or_404(ProjectMember, project=project, member_id=member_id)
        
        response = request.POST.get('response')
        notification_id = request.POST.get('notification_id')
        
        # Récupérer la notification originale si elle existe
        notification = None
        if notification_id:
            try:
                notification = Notification.objects.get(id=notification_id, recipient=request.user)
            except Notification.DoesNotExist:
                pass
        
        if member.leave_request_status == 'pending':
            if response == 'approve':
                # Approuver le départ - supprimer le membre
                leaving_user = member.member
                member.delete()
                
                # Notification au membre qui quitte
                NotificationService.create_notification(
                    recipient=leaving_user,
                    notification_type='SYSTEM',
                    title=_('Leave request approved'),
                    message=_('Your request to leave the project « {} » has been approved.').format(project.title),
                    related_object=project
                )
                
                # Mettre à jour la notification originale
                if notification:
                    notification.response_given = True
                    notification.response = 'approve'
                    notification.read = True
                    notification.save()
                
                messages.success(request, _('Leave request approved. {} has been removed from the project.').format(leaving_user.full_name))
                
            elif response == 'reject':
                # Refuser le départ - réinitialiser le statut
                member.leave_request_status = 'rejected'
                member.save()
                
                # Notification au membre
                NotificationService.create_notification(
                    recipient=member.member,
                    notification_type='SYSTEM',
                    title=_('Leave request rejected'),
                    message=_('Your request to leave the project « {} » has been rejected by the coordinator.').format(project.title),
                    related_object=project
                )
                
                # Mettre à jour la notification originale
                if notification:
                    notification.response_given = True
                    notification.response = 'reject'
                    notification.read = True
                    notification.save()
                
                messages.success(request, _('Leave request rejected.'))
        
        # Rediriger vers les notifications si la demande vient de là
        if notification_id:
            return redirect('notifications:list')
        
        return redirect('projects:project_members', pk=pk)

class ProjectSearchView(LoginAndVerifiedRequiredMixin, ListView):
    model = Project
    template_name = 'project_search.html'
    context_object_name = 'projects'
    
    def get_queryset(self):
        query = self.request.GET.get('q')
        if query:
            return Project.objects.filter(
                Q(title__icontains=query) |
                Q(institution__name__icontains=query) |
                Q(coordinator__full_name__icontains=query)
            )
        else:
            return Project.objects.all()


class RemoveMemberView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        project = get_object_or_404(Project, pk=self.kwargs['pk'])
        return project.coordinator == self.request.user

    def post(self, request, pk, member_id):
        project = get_object_or_404(Project, pk=pk)
        member = get_object_or_404(ProjectMember, project=project, member_id=member_id)
        
        # Récupérer l'utilisateur membre avant la suppression
        removed_user = member.member
        
        # Supprimer le membre
        member.delete()
        
        # Envoyer une notification au membre retiré
        NotificationService.create_notification(
            recipient=removed_user,
            notification_type='SYSTEM',
            title=_('Removed from project'),
            message=_('You have been removed from the project « {} » by the coordinator.').format(project.title),
            related_object=project
        )
        
        messages.success(request, _('Member removed successfully.'))
        return redirect('projects:project_members', pk=pk)

class RespondToRequestView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        project = get_object_or_404(Project, pk=self.kwargs['pk'])
        return project.coordinator == self.request.user

    def post(self, request, pk, request_id):
        project = get_object_or_404(Project, pk=pk)
        join_request = get_object_or_404(ProjectMember, pk=request_id, project=project)
        
        response = request.POST.get('response')
        if response == 'accept':
            join_request.status = 'accepted'
            join_request.save()
            messages.success(request, _('Request accepted successfully.'))
            
            # Créer une notification pour le membre
            NotificationService.create_notification(
                recipient=join_request.member,
                title=_('Project Request Accepted'),
                message=_('Your request to join {} has been accepted.').format(project.title),
                notification_type='project_request_accepted',
                related_object=project
            )
        elif response == 'reject':
            join_request.status = 'rejected'
            join_request.save()
            messages.success(request, _('Request rejected successfully.'))
            
            # Créer une notification pour le membre
            NotificationService.create_notification(
                recipient=join_request.member,
                title=_('Project Request Rejected'),
                message=_('Your request to join {} has been rejected.').format(project.title),
                notification_type='project_request_rejected',
                related_object=project
            )
        
        return redirect('projects:project_detail', pk=pk)