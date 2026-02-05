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
from projects.models import Project, ProjectMember
from notifications.models import Notification
from notifications.services import NotificationService
from functools import wraps
from django.contrib.auth.decorators import login_required
from typing import TYPE_CHECKING, Any
import logging

if TYPE_CHECKING:
    from .models import CustomUser

logger = logging.getLogger(__name__)

User = get_user_model()


# --------------------------
# Mixins and Decorators
# --------------------------
class LoginAndVerifiedRequiredMixin(LoginRequiredMixin):
    """
    Mixin that requires user to be logged in AND verified.
    Staff users bypass verification requirement.
    """
    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        user = request.user
        if hasattr(user, 'is_verified') and not user.is_verified and not user.is_staff:
            messages.warning(request, _("Your account is pending verification. Please wait for admin approval."))
            return redirect('accounts:awaiting_verification')
        return super().dispatch(request, *args, **kwargs)


def login_and_verified_required(view_func: Any) -> Any:
    """
    Decorator that requires user to be logged in AND verified.
    Staff users bypass verification requirement.
    """
    @wraps(view_func)
    def _wrapped_view(request: Any, *args: Any, **kwargs: Any) -> Any:
        if not request.user.is_authenticated:
            messages.info(request, _("Please log in to access this page."))
            return redirect('account_login')
        user = request.user
        if hasattr(user, 'is_verified') and not user.is_verified and not user.is_staff:
            messages.warning(request, _("Your account is pending verification. Please wait for admin approval."))
            return redirect('accounts:awaiting_verification')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# --------------------------
# SignUp View (Enhanced)
# --------------------------
class SignUp(CreateView):
    """
    User registration view with enhanced validation and security.
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
            # Create user
            user = form.save(commit=False)
            user.email = email  # Ensure normalized email
            user.is_active = True
            if hasattr(user, 'is_verified'):
                user.is_verified = True  # Auto-verify for now
            if hasattr(user, 'is_email_verified'):
                user.is_email_verified = True
            if hasattr(user, 'status'):
                user.status = 'active'
            user.save()

            # Log the user in using allauth backend
            login(self.request, user, backend='allauth.account.auth_backends.AuthenticationBackend')
            
            logger.info(f"New user registered: {email}")
            messages.success(self.request, _("Welcome! Your account has been created successfully."))
            return redirect('pages:home')
            
        except Exception as e:
            logger.error(f"Error creating user account: {str(e)}")
            messages.error(self.request, _("An error occurred while creating your account. Please try again."))
            return self.form_invalid(form)

    def form_invalid(self, form: Any) -> Any:
        messages.error(self.request, _("Please correct the errors below."))
        return super().form_invalid(form)


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
# Project Invitation View
# --------------------------
class InviteToProjectView(LoginRequiredMixin, View):
    """
    Handle sending project invitations to users.
    """
    def post(self, request: Any, pk: Any) -> Any:
        user_to_invite = get_object_or_404(User, pk=pk)
        project_id = request.POST.get('project_id')
        project = get_object_or_404(Project, pk=project_id, coordinator=request.user)

        # Check if user is already a member or has pending invitation
        if not ProjectMember.objects.filter(project=project, member=user_to_invite).exists():
            ProjectMember.objects.create(
                project=project,
                member=user_to_invite,
                role='member',
                status='pending'
            )

            # Get display name safely
            invite_user_name = getattr(user_to_invite, 'get_full_name_display', None)
            if invite_user_name is None:
                invite_user_name = str(user_to_invite)
            
            request_user_name = getattr(request.user, 'get_full_name_display', None)
            if request_user_name is None:
                request_user_name = str(request.user)

            # Create invitation notification
            NotificationService.create_notification(
                recipient=user_to_invite,
                notification_type='PROJECT_INVITE',
                title=_("Project Invitation"),
                message=_("You have been invited to join the project '%(project)s' by %(user)s.") % {
                    'project': project.title,
                    'user': request_user_name
                },
                project_id=project.pk,
                sender_id=request.user.id
            )

            messages.success(request, _("Invitation sent to %(name)s.") % {'name': invite_user_name})
        else:
            invite_user_name = getattr(user_to_invite, 'get_full_name_display', None)
            if invite_user_name is None:
                invite_user_name = str(user_to_invite)
            messages.warning(request, _("%(name)s is already a member or has a pending invitation.") % {'name': invite_user_name})
        return redirect('accounts:profile', pk=pk)


# --------------------------
# Project Invitation Response View
# --------------------------
class RespondToProjectInviteView(LoginRequiredMixin, View):
    """
    Handle user responses to project invitations.
    """
    def post(self, request: Any, project_id: Any) -> Any:
        project = get_object_or_404(Project, pk=project_id)
        member = ProjectMember.objects.filter(project=project, member=request.user, status='pending').first()

        if not member:
            messages.error(request, _("No pending invitation found for this project."))
            return redirect('projects:project_detail', pk=project_id)

        response = request.POST.get('response')
        notification_id = request.POST.get('notification_id')

        notification = None
        if notification_id:
            try:
                notification = Notification.objects.get(id=notification_id, recipient=request.user)
            except Notification.DoesNotExist:
                pass

        # Get display name safely
        request_user_name = getattr(request.user, 'get_full_name_display', None)
        if request_user_name is None:
            request_user_name = str(request.user)

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
                message=_("%(user)s has accepted the invitation to join the project '%(project)s'.") % {
                    'user': request_user_name,
                    'project': project.title
                },
                project_id=project.pk,
                sender_id=request.user.id
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
                message=_("%(user)s has declined the invitation to join the project '%(project)s'.") % {
                    'user': request_user_name,
                    'project': project.title
                },
                project_id=project.pk,
                sender_id=request.user.id
            )
            messages.info(request, _("You have declined the invitation."))

        return redirect('projects:project_detail', pk=project_id)


# --------------------------
# Other Views
# --------------------------
def awaiting_verification_view(request: Any) -> Any:
    """
    Display page for users awaiting verification.
    """
    if request.user.is_authenticated:
        if hasattr(request.user, 'is_verified') and request.user.is_verified:
            return redirect('pages:home')
    return render(request, 'awaiting_verification.html')


@login_required
def delete_account(request: Any) -> Any:
    """
    Handle account deletion with confirmation.
    """
    if request.method == 'POST':
        user = request.user
        email = getattr(user, 'email', str(user))
        
        # Log the account deletion
        logger.info(f"Account deleted: {email}")
        
        # Logout and delete user
        logout(request)
        user.delete()
        
        messages.success(request, _('Your account has been deleted successfully.'))
        return redirect('pages:home')
    
    return render(request, 'accounts/delete_account.html')
