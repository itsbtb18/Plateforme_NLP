from django.views.generic import CreateView, DetailView, UpdateView
from django.urls import reverse_lazy, reverse
from .forms import CustomUserCreationForm, CustomUserChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model, login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.translation import gettext as _
from django.utils import timezone
from django.views import View
from projects.models import Project, ProjectMember
from notifications.models import Notification
from notifications.services import NotificationService
from functools import wraps
from django.contrib.auth.decorators import login_required
from .two_factor_models import TwoFactorAuth
from .two_factor_utils import generate_otp, store_otp
from .two_factor_email import send_otp_email
import logging

logger = logging.getLogger(__name__)


# --------------------------
# Mixins et décorateurs
# --------------------------
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


# --------------------------
# Vue d’inscription (simplifiée)
# --------------------------
class SignUp(CreateView):
    form_class = CustomUserCreationForm
    template_name = 'account/signup.html'
    success_url = reverse_lazy('account_login')  # Redirige vers la page de connexion après succès

    def form_valid(self, form):
        # Vérifier si l'email existe déjà
        email = form.cleaned_data.get('email')
        User = get_user_model()
        if User.objects.filter(email=email).exists():
            messages.error(self.request, "This email is already in use. Please choose another one.")
            return self.form_invalid(form)

        # Créer l'utilisateur
        user = form.save(commit=False)
        user.is_active = True  # Activer le compte directement
        if hasattr(user, 'is_email_verified'):
            user.is_email_verified = True
        user.save()

        logger.info(f"✅ NEW USER CREATED: {user.email}")
        
        # ===== TRIGGER 2FA FOR NEW SIGNUP =====
        try:
            # Create TwoFactorAuth record with 2FA ENABLED
            two_fa, created = TwoFactorAuth.objects.get_or_create(
                user=user,
                defaults={'is_enabled': True}
            )
            logger.info(f"🔐 TwoFactorAuth record created for {user.email}: is_enabled={two_fa.is_enabled}")
            
            # Generate OTP and store in Redis
            otp_code = generate_otp()
            store_otp(str(user.id), otp_code)
            logger.info(f"📦 OTP stored in Redis for {user.email}")
            
            # Send OTP email
            send_otp_email(user.email, user.get_full_name(), otp_code)
            logger.info(f"📧 OTP email sent to {user.email}")
            
            # Mark user as pending 2FA verification
            self.request.session['pending_2fa_user_id'] = str(user.id)
            self.request.session.modified = True
            logger.info(f"🚀 User {user.email} marked as pending 2FA, redirecting to verify page")
            
            # Redirect to 2FA verification instead of login
            return redirect('accounts:verify_2fa')
            
        except Exception as e:
            logger.error(f"❌ 2FA setup error for {user.email}: {str(e)}")
            messages.error(self.request, "Error setting up 2FA. Please try again.")
            return redirect('accounts:account_login')


# --------------------------
# Vue profil utilisateur
# --------------------------
class ProfileView(LoginRequiredMixin, DetailView):
    model = get_user_model()
    template_name = 'account/profile.html'
    context_object_name = 'user'


# --------------------------
# Vue modification du profil
# --------------------------
class ProfileEditView(LoginRequiredMixin, UpdateView):
    model = get_user_model()
    form_class = CustomUserChangeForm
    template_name = 'account/profile_edit.html'
    context_object_name = 'user'

    def get_success_url(self):
        return reverse_lazy('accounts:profile', kwargs={'pk': self.object.pk})


# --------------------------
# Vue invitation à un projet
# --------------------------
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

            # Notification d’invitation
            NotificationService.create_notification(
                recipient=user_to_invite,
                notification_type='PROJECT_INVITE',
                title="Invitation à rejoindre un projet",
                message=f"Vous avez été invité(e) à rejoindre le projet « {project.title} » par {request.user.full_name}.",
                project_id=project.pk,
                sender_id=request.user.id
            )

            messages.success(request, f"Invitation envoyée à {user_to_invite.full_name}.")
        else:
            messages.warning(request, f"{user_to_invite.full_name} est déjà membre ou a déjà une invitation en attente.")
        return redirect('accounts:profile', pk=pk)


# --------------------------
# Vue réponse à une invitation
# --------------------------
class RespondToProjectInviteView(LoginRequiredMixin, View):
    def post(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        member = ProjectMember.objects.filter(project=project, member=request.user, status='pending').first()

        if not member:
            messages.error(request, "Aucune invitation en attente pour ce projet.")
            return redirect('projects:project_detail', pk=project_id)

        response = request.POST.get('response')
        notification_id = request.POST.get('notification_id')

        notification = None
        if notification_id:
            try:
                notification = Notification.objects.get(id=notification_id, recipient=request.user)
            except Notification.DoesNotExist:
                pass

        if response == 'accept':
            member.status = 'accepted'
            member.save()

            if notification:
                notification.response_given = True
                notification.response = 'accept'
                notification.response_date = timezone.now()
                notification.save()

            NotificationService.create_notification(
                recipient=project.coordinator,
                notification_type='PROJECT_INVITE_ACCEPTED',
                title="Invitation acceptée",
                message=f"{request.user.full_name} a accepté l'invitation à rejoindre le projet « {project.title} ».",
                project_id=project.pk,
                sender_id=request.user.id
            )
            messages.success(request, f"Vous avez rejoint le projet « {project.title} ».")

        elif response == 'reject':
            member.status = 'rejected'
            member.save()

            if notification:
                notification.response_given = True
                notification.response = 'reject'
                notification.response_date = timezone.now()
                notification.save()

            NotificationService.create_notification(
                recipient=project.coordinator,
                notification_type='PROJECT_INVITE_REJECTED',
                title="Invitation refusée",
                message=f"{request.user.full_name} a refusé l'invitation à rejoindre le projet « {project.title} ».",
                project_id=project.pk,
                sender_id=request.user.id
            )
            messages.info(request, "Vous avez refusé l'invitation.")

        return redirect('projects:project_detail', pk=project_id)


# --------------------------
# Autres vues
# --------------------------
def awaiting_verification_view(request):
    return render(request, 'awaiting_verification.html')


@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, _('Votre compte a été supprimé avec succès.'))
        return redirect('pages:home')
    return render(request, 'accounts/delete_account.html')


def custom_logout(request):
    """
    Custom logout view that shows logout confirmation page
    On POST, clears 2FA session before logging out
    """
    if request.method == 'POST':
        # Clear pending 2FA session
        if 'pending_2fa_user_id' in request.session:
            del request.session['pending_2fa_user_id']
        
        request.session.save()
        logout(request)
        messages.success(request, _('You have been logged out.'))
        return redirect('pages:home')
    
    # GET request - show logout confirmation page
    return render(request, 'account/logout.html')

