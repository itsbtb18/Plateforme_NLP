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
from django.http import HttpResponseForbidden
from django.core.exceptions import PermissionDenied
from typing import Any, TYPE_CHECKING, cast
from projects.models import Project, ProjectMember
from notifications.models import Notification
from notifications.services import NotificationService
from functools import wraps
from django.contrib.auth.decorators import login_required
from .two_factor_models import TwoFactorAuth
from .two_factor_utils import generate_otp, store_otp
from .two_factor_email import send_otp_email
import logging

# Import allauth LoginView
from allauth.account.views import LoginView as AllauthLoginView

if TYPE_CHECKING:
    from .models import CustomUser

logger = logging.getLogger(__name__)

User = get_user_model()


# --------------------------
# Mixins et décorateurs
# --------------------------
class LoginAndVerifiedRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        user = request.user
        is_verified = getattr(user, 'is_verified', True)
        if not is_verified and not user.is_staff:
            return redirect('accounts:awaiting_verification')
        return super().dispatch(request, *args, **kwargs)


def login_and_verified_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')
        user = request.user
        if hasattr(user, 'is_verified') and not user.is_verified and not user.is_staff:
            return redirect('accounts:awaiting_verification')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# --------------------------
# Vue d’inscription (simplifiée)
# --------------------------
class SignUp(CreateView):
    """
    User registration view with enhanced validation, security, and 2FA.
    """
    form_class = CustomUserCreationForm
    template_name = 'account/signup.html'
    success_url = reverse_lazy('pages:home')

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        # Redirect authenticated users to home
        if request.user.is_authenticated:
            messages.info(request, _("You are already logged in."))
            return redirect('pages:home')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: Any) -> Any:
        # Get and normalize email
        email = form.cleaned_data.get('email', '').lower().strip()

        # Check for existing email (case-insensitive)
        if User.objects.filter(email__iexact=email).exists():
            messages.error(self.request, _("This email is already registered. Please use a different email or try logging in."))
            logger.warning(f"Signup attempt with existing email: {email}")
            return self.form_invalid(form)

        try:
            # Create user (commit=False to prepare, then save separately)
            user = form.save(commit=False)
            user.email = email  # Ensure normalized email
            user.is_active = True
            if hasattr(user, 'is_verified'):
                user.is_verified = True  # Auto-verify for now
            if hasattr(user, 'is_email_verified'):
                user.is_email_verified = True
            if hasattr(user, 'status'):
                user.status = 'active'

            # Save user — catch ES indexing errors (user still saved to DB)
            try:
                user.save()
            except Exception as save_err:
                # post_save ES signal may raise even though DB write succeeded
                if User.objects.filter(pk=user.pk).exists():
                    logger.warning(f"ES indexing error (user saved OK): {save_err}")
                else:
                    raise

            logger.info(f"New user registered: {user.email}")

            # ===== TRIGGER 2FA FOR NEW SIGNUP =====
            try:
                # Create TwoFactorAuth record with 2FA ENABLED
                two_fa, created = TwoFactorAuth.objects.get_or_create(
                    user=user,
                    defaults={'is_enabled': True}
                )
                logger.info(f"TwoFactorAuth record created for {user.email}: is_enabled={two_fa.is_enabled}")

                # Generate OTP and store in Redis
                otp_code = generate_otp()
                store_otp(str(user.id), otp_code)
                logger.info(f"OTP stored in Redis for {user.email}")

                # Send OTP email
                send_otp_email(user.email, user.get_full_name(), otp_code)
                logger.info(f"OTP email sent to {user.email}")

                # Mark user as pending 2FA verification
                self.request.session['pending_2fa_user_id'] = str(user.id)
                self.request.session.modified = True
                logger.info(f"User {user.email} marked as pending 2FA, redirecting to verify page")

                # Redirect to 2FA verification instead of login
                return redirect('accounts:verify_2fa')

            except Exception as e:
                logger.error(f"2FA setup error for {user.email}: {str(e)}")
                # Fall back to direct login if 2FA fails
                login(self.request, user, backend='allauth.account.auth_backends.AuthenticationBackend')
                messages.success(self.request, _("Welcome! Your account has been created successfully."))
                return redirect('pages:home')

        except Exception as e:
            logger.error(f"User creation error: {str(e)}")
            messages.error(self.request, _("An error occurred during registration. Please try again."))
            return self.form_invalid(form)

    def form_invalid(self, form: Any) -> Any:
        messages.error(self.request, _("Please correct the errors below."))
        return super().form_invalid(form)


# --------------------------
# Custom Login View with Remember Me
# --------------------------
class LoginView(AllauthLoginView):
    """
    Custom login view with 2FA and Remember Me support.
    After password check, if 2FA is enabled, redirect to OTP verification
    instead of completing the login.
    """

    def form_valid(self, form: Any) -> Any:
        user = form.user  # allauth form provides authenticated user

        # Check if 2FA is enabled for this user
        try:
            two_fa = TwoFactorAuth.objects.get(user=user)
            if two_fa.is_enabled:
                # Generate OTP, store, and send email
                otp_code = generate_otp()
                store_otp(str(user.id), otp_code)
                send_otp_email(user.email, user.get_full_name(), otp_code)

                # Save pending state and remember-me preference
                self.request.session['pending_2fa_user_id'] = str(user.id)
                self.request.session['pending_2fa_remember'] = bool(self.request.POST.get('remember'))
                self.request.session.modified = True

                logger.info(f"2FA triggered for login: {user.email}")
                return redirect('accounts:verify_2fa')
        except TwoFactorAuth.DoesNotExist:
            pass

        # No 2FA — proceed with normal login
        response = super().form_valid(form)

        remember = self.request.POST.get('remember')
        if remember:
            self.request.session.set_expiry(None)
        else:
            self.request.session.set_expiry(0)

        return response


# --------------------------
# Profile View
# --------------------------
class ProfileView(LoginRequiredMixin, DetailView):
    """
    Display user profile with public information.
    """
    model = User
    template_name = 'account/profile.html'
    context_object_name = 'profile_user'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        profile_user = self.get_object()

        # Check if viewing own profile
        context['is_own_profile'] = self.request.user == profile_user

        # Get user's projects if viewing own profile
        if context['is_own_profile']:
            context['user_projects'] = Project.objects.filter(
                members__member=profile_user,
                members__status='accepted'
            ).distinct()[:5]

        return context


# --------------------------
# Profile Edit View (Enhanced)
# --------------------------
class ProfileEditView(LoginRequiredMixin, UpdateView):
    """
    Allow users to edit their own profile.
    """
    model = User
    form_class = CustomUserChangeForm
    template_name = 'account/profile_edit.html'
    context_object_name = 'profile_user'

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        # Ensure users can only edit their own profile
        obj = self.get_object()
        if obj != request.user and not request.user.is_staff:
            messages.error(request, _("You can only edit your own profile."))
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self) -> str:
        messages.success(self.request, _("Your profile has been updated successfully."))
        return reverse('accounts:profile', kwargs={'pk': self.get_object().pk})

    def form_invalid(self, form: Any) -> Any:
        messages.error(self.request, _("Please correct the errors in the form."))
        return super().form_invalid(form)


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
                title=_("Project Invitation"),
                message=_("You have been invited to join the project '%(project)s' by %(user)s."),
                project_id=project.pk,
                sender_id=request.user.id,
                message_kwargs={
                    'project': project.title,
                    'user': getattr(request.user, 'full_name', str(request.user))
                }
            )

            messages.success(request, _("Invitation sent to %(name)s.") % {'name': getattr(user_to_invite, 'full_name', str(user_to_invite))})
        else:
            messages.warning(request, _("%(name)s is already a member or has a pending invitation.") % {'name': getattr(user_to_invite, 'full_name', str(user_to_invite))})
        return redirect('accounts:profile', pk=pk)


# --------------------------
# Vue réponse à une invitation
# --------------------------
class RespondToProjectInviteView(LoginRequiredMixin, View):
    def post(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        member = ProjectMember.objects.filter(project=project, member=request.user, status='pending').first()

        if not member:
            messages.error(request, _("No pending invitation for this project."))
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
                title=_("Invitation Accepted"),
                message=_("%(user)s has accepted the invitation to join the project '%(project)s'."),
                project_id=project.pk,
                sender_id=request.user.id,
                message_kwargs={
                    'user': getattr(request.user, 'full_name', str(request.user)),
                    'project': project.title
                }
            )
            messages.success(request, _("You have joined the project '%(project)s'.") % {'project': project.title})

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
                title=_("Invitation Declined"),
                message=_("%(user)s has declined the invitation to join the project '%(project)s'."),
                project_id=project.pk,
                sender_id=request.user.id,
                message_kwargs={
                    'user': getattr(request.user, 'full_name', str(request.user)),
                    'project': project.title
                }
            )
            messages.info(request, _("You have declined the invitation."))

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

