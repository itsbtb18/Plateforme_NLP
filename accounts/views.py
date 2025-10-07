from django.views.generic import CreateView ,  DetailView , UpdateView
from django.urls import reverse_lazy
from .forms import CustomUserCreationForm  , CustomUserChangeForm, EmailVerificationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.contrib.auth import login, logout
from django.http import HttpResponse, HttpResponseRedirect
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from projects.models import Project, ProjectMember
from notifications.models import Notification
from notifications.services import NotificationService
from functools import wraps
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _

class LoginAndVerifiedRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_verified and not request.user.is_staff:
            return redirect('accounts:awaiting_verification')
        return super().dispatch(request, *args, **kwargs)

def login_and_verified_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')
        if not request.user.is_verified and not request.user.is_staff:
            return redirect('accounts:awaiting_verification')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

class SignUp(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('accounts:email_verification_prompt')
    template_name = 'account/signup.html'

    def form_valid(self, form):
        user, _ = form.save(self.request)  # Déballage du tuple
        user.is_active = False  # désactive le compte temporairement
        user.generate_verification_code()
        
        # Envoi de l'email avec le code
        send_mail(
            subject='Verifying your email address',
            message=f'Your verification code is : {user.email_verification_code}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )

        self.request.session['user_id_to_verify'] = str(user.pk)
        return redirect('accounts:email_verification_prompt')  # nouvelle vue

class ProfileView(LoginRequiredMixin,DetailView):
    model = get_user_model()
    template_name = 'account/profile.html'
    context_object_name = 'user'

class ProfileEditView(LoginRequiredMixin, UpdateView):
   model = get_user_model()
   form_class = CustomUserChangeForm
   template_name='account/profile_edit.html'
   context_object_name = 'user'
   def get_success_url(self):
    return reverse_lazy('accounts:profile', kwargs={'pk': self.object.pk})

class EmailVerificationView(View):
    form_class = EmailVerificationForm
    template_name = 'account/email_verification.html'

    def get(self, request):
        return render(request, self.template_name, {'form': self.form_class()})

    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            user_id = request.session.get('user_id_to_verify')
            user = get_object_or_404(get_user_model(), pk=user_id)

            if user.email_verification_code == code:
                user.is_active = True
                user.is_email_verified = True
                user.email_verification_code = ''
                user.save()
                messages.success(request, "Email verified successfully. You can now log in.")
                return redirect('account_login')  # Changé de 'auth:account_login' à 'account_login'
            else:
                messages.error(request, "Incorrect code. Try again..")
        return render(request, self.template_name, {'form': form})

class InviteToProjectView(LoginRequiredMixin, View):
    def post(self, request, pk):
        user_to_invite = get_object_or_404(get_user_model(), pk=pk)
        project_id = request.POST.get('project_id')
        project = get_object_or_404(Project, pk=project_id, coordinator=request.user)
        # Vérifier que l'utilisateur n'est pas déjà membre ou invité
        if not ProjectMember.objects.filter(project=project, member=user_to_invite).exists():
            ProjectMember.objects.create(
                project=project,
                member=user_to_invite,
                role='member',
                status='pending'
            )
            # Utiliser NotificationService pour envoyer l'invitation
            NotificationService.create_notification(
                recipient=user_to_invite,
                notification_type='PROJECT_INVITE',
                title="Invitation to join a project",
                message=f"You have been invited to join the project « {project.title} » by {request.user.full_name}.",
                project_id=project.pk,
                sender_id=request.user.id
            )
            messages.success(request, f"Invitation sent to {user_to_invite.full_name}.")
        else:
            messages.warning(request, f"{user_to_invite.full_name} is already a member or already has a pending invitation.")
        return redirect('accounts:profile', pk=pk)

class RespondToProjectInviteView(LoginRequiredMixin, View):
    def post(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        member = ProjectMember.objects.filter(project=project, member=request.user, status='pending').first()
        
        if not member:
            messages.error(request, "No invitations pending for this project.")
            return redirect('projects:project_detail', pk=project_id)
        
        response = request.POST.get('response')
        notification_id = request.POST.get('notification_id')
        
        # Récupérer la notification pour la mettre à jour
        notification = None
        if notification_id:
            try:
                notification = Notification.objects.get(
                    id=notification_id, 
                    recipient=request.user
                )
            except Notification.DoesNotExist:
                pass
        
        if response == 'accept':
            member.status = 'accepted'
            member.save()
            
            # Mettre à jour la notification
            if notification:
                notification.response_given = True
                notification.response = 'accept'
                notification.response_date = timezone.now()
                notification.save()
            
            # Utiliser NotificationService pour la notification d'acceptation
            NotificationService.create_notification(
                recipient=project.coordinator,
                notification_type='PROJECT_INVITE_ACCEPTED',
                title="Invitation accepted",
                message=f"{request.user.full_name} accepted the invitation to join the project « {project.title} ».",
                project_id=project.pk,
                sender_id=request.user.id
            )
            messages.success(request, f"You have joined the project « {project.title} ».")
            
        elif response == 'reject':
            member.status = 'rejected'
            member.save()
            
            # Mettre à jour la notification
            if notification:
                notification.response_given = True
                notification.response = 'reject'
                notification.response_date = timezone.now()
                notification.save()
            
            # Utiliser NotificationService pour la notification de refus
            NotificationService.create_notification(
                recipient=project.coordinator,
                notification_type='PROJECT_INVITE_REJECTED',
                title="Invitation refused",
                message=f"{request.user.full_name} declined the invitation to join the project « {project.title} ».",
                project_id=project.pk,
                sender_id=request.user.id
            )
            messages.info(request, f"You declined the invitation.")
        
        return redirect('projects:project_detail', pk=project_id)
def awaiting_verification_view(request):
    return render(request, 'awaiting_verification.html')

@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, _('Your account has been successfully deleted.'))
        return redirect('pages:home')
    return render(request, 'accounts/delete_account.html')