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
from .two_factor_utils import generate_otp, store_otp
from .two_factor_email import send_otp_email
from .two_factor_models import TwoFactorAuth
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

        # Handle existing users: allow re-registration if inactive & unverified
        existing = User.objects.filter(email__iexact=email).first()
        if existing:
            if existing.is_active:
                messages.error(self.request, _("This email is already registered. Please use a different email or try logging in."))
                logger.warning(f"Signup attempt with existing active email: {email}")
                return self.form_invalid(form)
            else:
                # Inactive, unverified account — delete so user can re-register
                logger.info(f"Removing inactive account for re-registration: {email}")
                existing.delete()

        try:
            # Create user with is_active=False (activated after 2FA verification)
            user = form.save(commit=False)
            user.email = email
            user.is_active = False
            if hasattr(user, 'is_verified'):
                user.is_verified = False
            if hasattr(user, 'is_email_verified'):
                user.is_email_verified = False
            if hasattr(user, 'status'):
                user.status = 'pending'

            try:
                user.save()
            except Exception as save_err:
                if User.objects.filter(pk=user.pk).exists():
                    logger.warning(f"ES indexing error (user saved OK): {save_err}")
                else:
                    raise

            logger.info(f"New user registered (pending 2FA): {user.email}")

            # Create TwoFactorAuth record
            TwoFactorAuth.objects.get_or_create(user=user, defaults={'is_enabled': True})

            # Generate OTP, store in Redis, and send email
            otp_code = generate_otp()
            store_otp(str(user.id), otp_code)
            send_otp_email(user.email, user.get_full_name(), otp_code)

            # Store user ID in session for 2FA verification
            self.request.session['pending_2fa_user_id'] = str(user.id)
            self.request.session['pending_2fa_is_signup'] = True
            self.request.session.modified = True

            return redirect('accounts:verify_2fa')

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
    Custom login view with Remember Me support.
    """

    def form_valid(self, form: Any) -> Any:
        response = super().form_valid(form)

        remember = self.request.POST.get('remember')
        if remember:
            self.request.session.set_expiry(None)  # Use SESSION_COOKIE_AGE (2 weeks)
        else:
            self.request.session.set_expiry(0)  # Expire when browser closes

        return response


# --------------------------
# Profile View
# --------------------------
class ProfileView(DetailView):
    """
    Public user profile view showing user information and contributions.
    """
    model = User
    template_name = 'account/profile.html'
    context_object_name = 'user'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        profile_user = self.get_object()

        context['is_own_profile'] = (
            self.request.user.is_authenticated and self.request.user == profile_user
        )

        # User's projects
        context['user_projects'] = Project.objects.filter(
            members__member=profile_user,
            members__status='accepted'
        ).distinct()[:6]

        # User's posts (QA)
        from QA.models import Post
        context['user_posts'] = Post.objects.filter(
            author=profile_user, approval_status='approved'
        ).order_by('-created_at')[:6]

        # User's courses (as teacher)
        from resources.models import Course
        context['user_courses'] = Course.objects.filter(
            teacher=profile_user, approval_status='approved'
        ).order_by('-creation_date')[:6]

        # User's documents (as author) - articles, theses, memoirs
        from resources.models import Document
        context['user_resources'] = Document.objects.filter(
            author=profile_user, approval_status='approved'
        ).order_by('-creation_date')[:6]

        # User's forum topics
        from forum.models import Topic
        context['user_topics'] = Topic.objects.filter(
            creator=profile_user, approval_status='approved'
        ).order_by('-created_at')[:6]

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

    def form_valid(self, form):
        import os as _os
        user = form.save(commit=False)
        # Avatar removal
        if self.request.POST.get('avatar-clear') == 'on':
            if user.avatar:
                if user.avatar.storage.exists(user.avatar.name):
                    user.avatar.storage.delete(user.avatar.name)
                user.avatar = None
        # Avatar upload
        avatar_file = self.request.FILES.get('avatar')
        if avatar_file:
            if avatar_file.size > 2 * 1024 * 1024:
                form.add_error(None, _("Image file size must be less than 2MB."))
                return self.form_invalid(form)
            allowed = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
            ext = _os.path.splitext(avatar_file.name)[1].lstrip('.').lower()
            if ext not in allowed:
                form.add_error(None, _("Allowed image formats: %(formats)s") % {'formats': ', '.join(sorted(allowed))})
                return self.form_invalid(form)
            if user.avatar:
                if user.avatar.storage.exists(user.avatar.name):
                    user.avatar.storage.delete(user.avatar.name)
            user.avatar = avatar_file
        user.save()
        return redirect(self.get_success_url())

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
        # Soft delete: anonymize user data instead of hard delete
        user.email = f"deleted_{user.id}@deleted.local"
        user.full_name = ''
        user.full_name_ar = ''
        user.full_name_en = ''
        user.bio = ''
        user.bio_ar = ''
        user.bio_en = ''
        user.avatar = None
        user.linkedin_url = None
        user.twitter_url = None
        user.facebook_url = None
        user.is_active = False
        user.status = 'blocked'
        user.set_unusable_password()
        user.save()
        logout(request)
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

