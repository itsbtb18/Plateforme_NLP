import logging
import time
from functools import wraps
from typing import Any

# Import allauth LoginView
from allauth.account.views import LoginView as AllauthLoginView
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login as auth_login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import BooleanField, Exists, OuterRef, Q, Value
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import CreateView, DetailView, UpdateView
from notifications.models import Notification
from notifications.services import LocalizedValue, NotificationService
from pages.security import log_admin_activity
from projects.models import Project, ProjectMember

from .forms import CustomUserChangeForm, CustomUserCreationForm
from .models import Follow, Friendship
from .two_factor_email import send_otp_email
from .two_factor_models import TwoFactorAuth
from .two_factor_utils import generate_otp, send_otp, store_otp

logger = logging.getLogger(__name__)

User = get_user_model()


def annotate_is_followed_by_me(queryset, viewer):
    """
    Annotate a user queryset with boolean field `is_followed_by_me`.
    """
    if viewer and viewer.is_authenticated:
        follow_subquery = Follow.objects.filter(
            follower=viewer,
            following=OuterRef("pk"),
        )
        return queryset.annotate(is_followed_by_me=Exists(follow_subquery))
    return queryset.annotate(
        is_followed_by_me=Value(False, output_field=BooleanField())
    )


# --------------------------
# Mixins et décorateurs
# --------------------------
class LoginAndVerifiedRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        user = request.user
        is_verified = getattr(user, "is_verified", True)
        if not is_verified and not user.is_staff:
            return redirect("accounts:awaiting_verification")
        return super().dispatch(request, *args, **kwargs)


def login_and_verified_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")
        user = request.user
        if hasattr(user, "is_verified") and not user.is_verified and not user.is_staff:
            return redirect("accounts:awaiting_verification")
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
    template_name = "account/signup.html"
    success_url = reverse_lazy("pages:home")

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        # Redirect authenticated users to home
        if request.user.is_authenticated:
            messages.info(request, _("You are already logged in."))
            return redirect("pages:home")
        # Clear any stale 2FA session data from a previous abandoned signup
        for key in [
            "pending_2fa_user_id",
            "pending_2fa_is_signup",
            "pending_2fa_remember",
        ]:
            request.session.pop(key, None)
        if request.session.modified:
            request.session.save()
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: Any) -> Any:
        # Get and normalize email
        email = form.cleaned_data.get("email", "").lower().strip()

        # Handle existing users: allow re-registration if inactive & unverified
        existing = User.objects.filter(email__iexact=email).first()
        if existing:
            if existing.is_active:
                messages.error(
                    self.request,
                    _(
                        "This email is already registered. Please use a different email or try logging in."
                    ),
                )
                logger.warning(f"Signup attempt with existing active email: {email}")
                return self.form_invalid(form)
            else:
                # Inactive, unverified account — delete so user can re-register
                logger.info(f"Removing inactive account for re-registration: {email}")
                existing.delete()

        user = None
        try:
            # Create user with is_active=False (activated after 2FA verification)
            user = form.save(commit=False)
            user.email = email
            user.is_active = False
            if hasattr(user, "is_verified"):
                user.is_verified = False
            if hasattr(user, "is_email_verified"):
                user.is_email_verified = False
            if hasattr(user, "status"):
                user.status = "pending"

            try:
                user.save()
            except Exception as save_err:
                if User.objects.filter(pk=user.pk).exists():
                    logger.warning(f"ES indexing error (user saved OK): {save_err}")
                else:
                    raise

            logger.info(f"New user registered (pending 2FA): {user.email}")

            # Create TwoFactorAuth record
            TwoFactorAuth.objects.get_or_create(
                user=user, defaults={"is_enabled": True}
            )

            # Generate OTP, store in Redis, and send email
            otp_code = generate_otp()
            store_otp(str(user.id), otp_code)
            send_otp_email(user.email, user.get_full_name(), otp_code)

            # Store user ID in session for 2FA verification
            self.request.session["pending_2fa_user_id"] = str(user.id)
            self.request.session["pending_2fa_is_signup"] = True
            self.request.session.modified = True

            return redirect("accounts:verify_2fa")

        except Exception as e:
            if user is not None and getattr(user, "pk", None):
                try:
                    User.objects.filter(pk=user.pk).delete()
                    logger.warning(
                        "Rolled back partially created signup user after failure: %s",
                        user.email,
                    )
                except Exception:
                    logger.exception("Failed to rollback partially created signup user")
            logger.error(f"User creation error: {str(e)}")
            messages.error(
                self.request,
                _("An error occurred during registration. Please try again."),
            )
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

    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_SECONDS = 15 * 60
    FAILURE_WINDOW_SECONDS = 15 * 60
    FAILURE_DELAY_SECONDS = 1.2

    def _client_ip(self) -> str:
        xff = (
            (self.request.META.get("HTTP_X_FORWARDED_FOR", "") or "")
            .split(",")[0]
            .strip()
        )
        return (xff or self.request.META.get("REMOTE_ADDR", "") or "unknown")[:64]

    def _email_key(self) -> str:
        email = (
            (self.request.POST.get("login") or self.request.POST.get("email") or "")
            .strip()
            .lower()
        )
        return email or "unknown"

    def _lock_key(self) -> str:
        return f"auth:login:lock:{self._client_ip()}:{self._email_key()}"

    def _fail_key(self) -> str:
        return f"auth:login:fail:{self._client_ip()}:{self._email_key()}"

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        # Clear any stale 2FA session data from an abandoned signup flow
        for key in [
            "pending_2fa_user_id",
            "pending_2fa_is_signup",
            "pending_2fa_remember",
        ]:
            request.session.pop(key, None)
        if request.session.modified:
            request.session.save()

        locked_until = cache.get(self._lock_key())
        if locked_until:
            messages.error(
                request,
                _("Too many failed attempts. Try again later."),
            )
            return self.render_to_response(self.get_context_data(form=self.get_form()))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: Any) -> Any:
        cache.delete(self._fail_key())
        cache.delete(self._lock_key())

        remember = bool(self.request.POST.get("remember"))
        login_value = (
            form.cleaned_data.get("login")
            or form.cleaned_data.get("email")
            or self.request.POST.get("login")
            or self.request.POST.get("email")
            or ""
        )
        password = form.cleaned_data.get("password") or self.request.POST.get(
            "password", ""
        )

        user = None
        if login_value and password:
            user = authenticate(
                self.request,
                username=login_value,
                password=password,
            )

        if user is None:
            # Fallback to allauth's authenticated user object from the validated form.
            user = getattr(form, "user", None) or getattr(form, "user_cache", None)

        if user is not None:
            two_fa = TwoFactorAuth.objects.filter(user=user, is_enabled=True).first()
            if two_fa is not None:
                self.request.session["pending_2fa_user_id"] = str(user.pk)
                self.request.session["pending_2fa_is_signup"] = False
                self.request.session["pending_2fa_remember"] = remember
                self.request.session.modified = True

                if two_fa.method == TwoFactorAuth.METHOD_EMAIL_OTP:
                    if not send_otp(user):
                        messages.error(
                            self.request,
                            _("Failed to send OTP. Please try again."),
                        )
                        return self.render_to_response(
                            self.get_context_data(form=self.get_form())
                        )

                return redirect("accounts:verify_2fa")

        # 2FA disabled -> normal login flow
        response = super().form_valid(form)

        if remember:
            self.request.session.set_expiry(None)  # Use SESSION_COOKIE_AGE (2 weeks)
        else:
            self.request.session.set_expiry(0)  # Expire when browser closes

        # Ensure an explicit login call in this branch as requested.
        if user is not None and not self.request.user.is_authenticated:
            auth_login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")

        if self.request.user.is_authenticated and getattr(
            self.request.user, "is_staff", False
        ):
            log_admin_activity(
                user=self.request.user,
                request=self.request,
                action="admin_login_success",
                target_type="auth",
            )

        return response

    def form_invalid(self, form: Any) -> Any:
        fail_key = self._fail_key()
        lock_key = self._lock_key()
        current_fails = cache.get(fail_key, 0) + 1
        cache.set(fail_key, current_fails, self.FAILURE_WINDOW_SECONDS)
        if current_fails >= self.MAX_LOGIN_ATTEMPTS:
            cache.set(lock_key, "1", self.LOCKOUT_SECONDS)
            messages.error(
                self.request,
                _("Account temporarily locked due to repeated failed attempts."),
            )

        time.sleep(self.FAILURE_DELAY_SECONDS)
        return super().form_invalid(form)


# --------------------------
# Profile View
# --------------------------
class ProfileView(DetailView):
    """
    Public user profile view showing user information and contributions.
    """

    model = User
    template_name = "account/profile.html"
    context_object_name = "user"

    @method_decorator(ensure_csrf_cookie)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        profile_user = self.get_object()
        viewer = self.request.user if self.request.user.is_authenticated else None
        selected_section = (self.request.GET.get("section") or "all").strip().lower()
        valid_sections = {
            "all",
            "posts",
            "courses",
            "resources",
            "tools",
            "corpora",
            "projects",
            "topics",
            "events_upcoming",
            "events_past",
            "events_created",
        }
        if selected_section not in valid_sections:
            selected_section = "all"

        is_own_profile = bool(viewer and viewer == profile_user)
        relation_state = Friendship.relation_state(viewer, profile_user)
        is_blocked_profile = relation_state == "BLOQUE"
        is_following_profile = bool(
            viewer
            and viewer != profile_user
            and Follow.objects.filter(follower=viewer, following=profile_user).exists()
        )
        if is_blocked_profile:
            is_following_profile = False
        can_view_full = is_own_profile or is_following_profile

        context["is_own_profile"] = is_own_profile
        context["relation_state"] = relation_state
        context["is_blocked_profile"] = is_blocked_profile
        context["is_friend"] = False
        context["can_view_full_profile"] = can_view_full
        context["can_view_contributions"] = True
        context["page"] = "profile"
        context["selected_section"] = selected_section
        context["followers_count"] = Follow.objects.filter(
            following=profile_user
        ).count()
        context["following_count"] = Follow.objects.filter(follower=profile_user).count()
        context["is_following_profile"] = is_following_profile

        # Public resources are always visible (profile public view)
        from resources.models import Document

        user_resources_qs = Document.objects.filter(author=profile_user).order_by(
            "-creation_date"
        )

        # Show user contributions publicly on profile pages
        user_projects_qs = Project.objects.filter(
            members__member=profile_user, members__status="accepted"
        ).distinct()

        from QA.models import Post

        user_posts_qs = Post.objects.filter(author=profile_user).order_by("-created_at")

        from resources.models import Corpus, Course, NLPTool

        user_courses_qs = Course.objects.filter(teacher=profile_user).order_by(
            "-creation_date"
        )

        user_corpora_qs = Corpus.objects.filter(author=profile_user).order_by(
            "-creation_date"
        )

        user_tools_qs = NLPTool.objects.filter(author=profile_user).order_by(
            "-creation_date"
        )

        from forum.models import Topic

        user_topics_qs = Topic.objects.filter(creator=profile_user).order_by(
            "-created_at"
        )

        from events.models import Event, EventRegistration

        today = timezone.now().date()
        regs = EventRegistration.objects.filter(user=profile_user).select_related(
            "event"
        )
        upcoming_events_qs = regs.filter(event__start_date__gte=today).order_by(
            "event__start_date"
        )
        past_events_qs = regs.filter(event__start_date__lt=today).order_by(
            "-event__start_date"
        )
        user_events_qs = Event.objects.filter(created_by=profile_user).order_by(
            "-start_date"
        )

        # Experience timeline: project participation roles + events
        privileged_view = bool(is_own_profile or (viewer and viewer.is_staff))

        coordinated_projects_qs = Project.objects.filter(coordinator=profile_user)
        project_memberships_qs = ProjectMember.objects.filter(
            member=profile_user,
            status="accepted",
        ).exclude(project__coordinator=profile_user)
        event_registrations_qs = EventRegistration.objects.filter(user=profile_user)
        created_events_exp_qs = Event.objects.filter(created_by=profile_user)

        if not privileged_view:
            coordinated_projects_qs = coordinated_projects_qs.filter(
                approval_status="approved"
            )
            project_memberships_qs = project_memberships_qs.filter(
                project__approval_status="approved"
            )
            event_registrations_qs = event_registrations_qs.filter(
                event__approval_status="approved"
            )
            created_events_exp_qs = created_events_exp_qs.filter(
                approval_status="approved"
            )

        experiences = []

        for project in coordinated_projects_qs.select_related("institution").order_by(
            "-created_at"
        ):
            experiences.append(
                {
                    "kind": "project",
                    "kind_label": _("Project"),
                    "icon": "fa-diagram-project",
                    "title": project.get_localized_title() or project.title,
                    "subtitle": getattr(project.institution, "name", "") or "",
                    "role": _("Coordinator"),
                    "description": project.get_localized_description() or "",
                    "url": reverse("projects:project_detail", kwargs={"pk": project.pk}),
                    "started_at": project.created_at,
                    "ended_at": None,
                    "sort_date": project.created_at.date(),
                }
            )

        for membership in project_memberships_qs.select_related(
            "project", "project__institution"
        ).order_by("-created_at"):
            project = membership.project
            experiences.append(
                {
                    "kind": "project",
                    "kind_label": _("Project"),
                    "icon": "fa-users",
                    "title": project.get_localized_title() or project.title,
                    "subtitle": getattr(project.institution, "name", "") or "",
                    "role": membership.role or _("Team Member"),
                    "description": project.get_localized_description() or "",
                    "url": reverse("projects:project_detail", kwargs={"pk": project.pk}),
                    "started_at": membership.created_at,
                    "ended_at": None,
                    "sort_date": membership.created_at.date(),
                }
            )

        for event in created_events_exp_qs.select_related("organizer").order_by(
            "-start_date"
        ):
            experiences.append(
                {
                    "kind": "event",
                    "kind_label": _("Event"),
                    "icon": "fa-calendar-plus",
                    "title": event.get_localized_title() or event.title,
                    "subtitle": event.get_localized_location() or "",
                    "role": _("Organizer"),
                    "description": event.get_localized_description() or "",
                    "url": reverse("events:event_detail", kwargs={"pk": event.pk}),
                    "started_at": event.start_date,
                    "ended_at": event.end_date,
                    "sort_date": event.start_date,
                }
            )

        for registration in event_registrations_qs.select_related("event").order_by(
            "-event__start_date"
        ):
            event = registration.event
            experiences.append(
                {
                    "kind": "event",
                    "kind_label": _("Event"),
                    "icon": "fa-calendar-check",
                    "title": event.get_localized_title() or event.title,
                    "subtitle": event.get_localized_location() or "",
                    "role": _("Participant"),
                    "description": event.get_localized_description() or "",
                    "url": reverse("events:event_detail", kwargs={"pk": event.pk}),
                    "started_at": event.start_date,
                    "ended_at": event.end_date,
                    "sort_date": event.start_date,
                }
            )

        experiences.sort(
            key=lambda item: item.get("sort_date") or timezone.now().date(),
            reverse=True,
        )
        context["user_experiences"] = experiences[:8]
        context["user_experiences_count"] = len(experiences)

        def section_items(queryset, section_key: str):
            if selected_section in ("all", section_key):
                return queryset if selected_section == section_key else queryset[:6]
            return queryset.none()

        context["user_posts"] = section_items(user_posts_qs, "posts")
        context["user_courses"] = section_items(user_courses_qs, "courses")
        context["user_resources"] = section_items(user_resources_qs, "resources")
        context["user_tools"] = section_items(user_tools_qs, "tools")
        context["user_corpora"] = section_items(user_corpora_qs, "corpora")
        context["user_projects"] = section_items(user_projects_qs, "projects")
        context["user_topics"] = section_items(user_topics_qs, "topics")
        context["upcoming_events"] = section_items(
            upcoming_events_qs, "events_upcoming"
        )
        context["past_events"] = section_items(past_events_qs, "events_past")
        context["user_events"] = section_items(user_events_qs, "events_created")

        # Profile headline stats for "social-pro" header
        context["user_projects_count"] = user_projects_qs.count()
        context["user_corpus_count"] = user_corpora_qs.count()
        context["user_news_count"] = user_posts_qs.count()
        context["user_courses_count"] = user_courses_qs.count()
        context["user_resources_count"] = user_resources_qs.count()
        context["user_tools_count"] = user_tools_qs.count()
        context["user_topics_count"] = user_topics_qs.count()
        context["upcoming_events_count"] = upcoming_events_qs.count()
        context["past_events_count"] = past_events_qs.count()
        context["user_events_count"] = user_events_qs.count()
        section_counts = {
            "posts": context["user_news_count"],
            "courses": context["user_courses_count"],
            "resources": context["user_resources_count"],
            "tools": context["user_tools_count"],
            "corpora": context["user_corpus_count"],
            "projects": context["user_projects_count"],
            "topics": context["user_topics_count"],
            "events_upcoming": context["upcoming_events_count"],
            "events_past": context["past_events_count"],
            "events_created": context["user_events_count"],
        }
        context["selected_section_count"] = section_counts.get(selected_section, 0)

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
    template_name = "account/profile_edit.html"
    context_object_name = "profile_user"

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        # Ensure users can only edit their own profile
        obj = self.get_object()
        if obj != request.user and not request.user.is_staff:
            messages.error(request, _("You can only edit your own profile."))
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self) -> str:
        messages.success(self.request, _("Your profile has been updated successfully."))
        return reverse("accounts:profile", kwargs={"pk": self.get_object().pk})

    def form_valid(self, form):
        import os as _os

        user = form.save(commit=False)
        # Avatar removal
        if self.request.POST.get("avatar-clear") == "on":
            if user.avatar:
                if user.avatar.storage.exists(user.avatar.name):
                    user.avatar.storage.delete(user.avatar.name)
                user.avatar = None
        # Avatar upload
        avatar_file = self.request.FILES.get("avatar")
        if avatar_file:
            if avatar_file.size > 2 * 1024 * 1024:
                form.add_error(None, _("Image file size must be less than 2MB."))
                return self.form_invalid(form)
            allowed = {"jpg", "jpeg", "png", "gif", "webp"}
            ext = _os.path.splitext(avatar_file.name)[1].lstrip(".").lower()
            if ext not in allowed:
                form.add_error(
                    None,
                    _("Allowed image formats: %(formats)s")
                    % {"formats": ", ".join(sorted(allowed))},
                )
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
class NetworkInvitationsView(LoginRequiredMixin, View):
    template_name = "account/network_requests.html"

    def get(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        Notification.objects.filter(
            recipient=request.user,
            type="FOLLOW_REQUEST",
            read=False,
        ).update(read=True, read_at=timezone.now())

        incoming = (
            Follow.objects.filter(following=request.user)
            .select_related("follower")
            .order_by("-created_at")
        )
        outgoing = (
            Follow.objects.filter(follower=request.user)
            .select_related("following")
            .order_by("-created_at")
        )
        following_ids = set(
            Follow.objects.filter(follower=request.user).values_list(
                "following_id", flat=True
            )
        )

        return render(
            request,
            self.template_name,
            {
                "incoming_requests": incoming,
                "outgoing_requests": outgoing,
                "following_ids": following_ids,
                "page": "network",
            },
        )


@login_required
def blocked_users_api(request: Any) -> Any:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    blocked = (
        Friendship.objects.filter(
            requester=request.user, status=Friendship.Status.BLOCKED
        )
        .select_related("addressee")
        .order_by("-created_at")
    )

    data = []
    for rel in blocked:
        u = rel.addressee
        avatar_url = ""
        if getattr(u, "avatar", None):
            try:
                avatar_url = u.avatar.url
            except Exception:
                avatar_url = ""
        data.append(
            {
                "id": str(u.id),
                "name": u.get_full_name_display,
                "avatar": avatar_url,
            }
        )
    return JsonResponse({"ok": True, "items": data})


@login_required
def invitations_count_api(request: Any) -> Any:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    follow_notifications_count = Notification.objects.filter(
        recipient=request.user,
        type__in=["FOLLOW_REQUEST", "MESSAGE"],
        read=False,
    ).filter(
        Q(type="FOLLOW_REQUEST") | Q(message_en__icontains="started following you")
    ).count()

    following_ids = Follow.objects.filter(follower=request.user).values_list(
        "following_id", flat=True
    )
    pending_followers_count = Follow.objects.filter(following=request.user).exclude(
        follower_id__in=following_ids
    ).count()

    return JsonResponse(
        {
            "ok": True,
            "count": max(follow_notifications_count, pending_followers_count),
            "follow_notifications_count": follow_notifications_count,
            "pending_followers_count": pending_followers_count,
        }
    )


@login_required
def follow_list_api(request: Any, user_id: str) -> Any:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    profile_user = get_object_or_404(User, pk=user_id)
    kind = (request.GET.get("kind") or "").strip().lower()
    if kind not in {"followers", "following"}:
        return JsonResponse({"ok": False, "error": _("Invalid list type.")}, status=400)

    if kind == "followers":
        relations = (
            Follow.objects.filter(following=profile_user)
            .select_related("follower")
            .order_by("-created_at")
        )
        users = [rel.follower for rel in relations]
    else:
        relations = (
            Follow.objects.filter(follower=profile_user)
            .select_related("following")
            .order_by("-created_at")
        )
        users = [rel.following for rel in relations]

    user_ids = [u.id for u in users]
    viewer_following_ids = set(
        Follow.objects.filter(
            follower=request.user,
            following_id__in=user_ids,
        ).values_list("following_id", flat=True)
    )
    is_own_profile = request.user == profile_user

    items = []
    for u in users:
        avatar_url = ""
        if getattr(u, "avatar", None):
            try:
                avatar_url = u.avatar.url
            except Exception:
                avatar_url = ""

        display_name = getattr(u, "get_full_name_display", None)
        if callable(display_name):
            display_name = display_name()
        if not display_name:
            display_name = getattr(u, "full_name", None) or u.email

        institution = getattr(u, "institution", None) or ""
        items.append(
            {
                "id": str(u.id),
                "name": str(display_name),
                "avatar": avatar_url,
                "institution": str(institution),
                "profile_url": reverse("accounts:profile", kwargs={"pk": u.id}),
                "is_followed_by_me": bool(u.id in viewer_following_ids),
                "is_own_profile": is_own_profile,
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "kind": kind,
            "items": items,
            "count": len(items),
        }
    )


@login_required
@require_POST
def remove_follower(request: Any, user_id: str) -> Any:
    target_user = get_object_or_404(User, pk=user_id)
    if target_user == request.user:
        return JsonResponse(
            {"ok": False, "error": _("You cannot remove yourself.")},
            status=400,
        )

    deleted, _ = Follow.objects.filter(
        follower=target_user,
        following=request.user,
    ).delete()

    return JsonResponse(
        {
            "ok": True,
            "deleted": bool(deleted),
            "followers_count": Follow.objects.filter(following=request.user).count(),
            "following_count": Follow.objects.filter(follower=request.user).count(),
        }
    )


@login_required
def set_online_visibility_api(request: Any) -> Any:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    raw = (request.POST.get("is_on") or "").strip().lower()
    if raw in {"1", "true", "on", "yes"}:
        is_on = True
    elif raw in {"0", "false", "off", "no"}:
        is_on = False
    else:
        return JsonResponse({"ok": False, "error": _("Invalid value.")}, status=400)

    request.user.show_online_status = is_on
    request.user.save(update_fields=["show_online_status"])
    return JsonResponse({"ok": True, "show_online_status": is_on})


@login_required
def friendship_action(request: Any, user_id: str, action: str) -> Any:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    target_user = get_object_or_404(User, pk=user_id)
    current_user = request.user

    if target_user == current_user:
        return JsonResponse(
            {"ok": False, "error": _("Invalid target user.")}, status=400
        )

    try:
        pair_filter = Q(requester=current_user, addressee=target_user) | Q(
            requester=target_user, addressee=current_user
        )
        blocked_relations = Friendship.objects.filter(
            pair_filter, status=Friendship.Status.BLOCKED
        )

        if action == "block":
            Friendship.objects.filter(pair_filter).delete()
            Follow.objects.filter(
                Q(follower=current_user, following=target_user)
                | Q(follower=target_user, following=current_user)
            ).delete()
            Friendship.objects.create(
                requester=current_user,
                addressee=target_user,
                status=Friendship.Status.BLOCKED,
            )
            state = "BLOQUE"

        elif action == "unblock":
            Friendship.objects.filter(
                requester=current_user,
                addressee=target_user,
                status=Friendship.Status.BLOCKED,
            ).delete()
            state = "NEUTRE"

        else:
            return JsonResponse(
                {
                    "ok": False,
                    "error": _(
                        "Follow management is enabled. Only block/unblock is allowed."
                    ),
                },
                status=400,
            )

        return JsonResponse(
            {"ok": True, "state": state, "target_id": str(target_user.id)}
        )
    except Exception as exc:
        logger.error("Friendship action failed: %s", exc, exc_info=True)
        return JsonResponse({"ok": False, "error": _("Action failed.")}, status=500)


@login_required
@require_POST
def follow_user(request: Any, user_id: str) -> Any:
    target_user = get_object_or_404(User, pk=user_id)
    if request.user == target_user:
        return JsonResponse(
            {"ok": False, "error": _("You cannot follow yourself.")},
            status=400,
        )
    relation = Friendship.between(request.user, target_user)
    if relation and relation.status == Friendship.Status.BLOCKED:
        return JsonResponse(
            {"ok": False, "error": _("You cannot follow this user.")},
            status=403,
        )

    _, created = Follow.objects.get_or_create(
        follower=request.user,
        following=target_user,
    )
    notification_sent = False
    if created:
        try:
            NotificationService.create_notification(
                recipient=target_user,
                notification_type="FOLLOW_REQUEST",
                title=_("New follower"),
                message=_("%(user)s started following you."),
                sender_id=request.user.id,
                message_kwargs={"user": LocalizedValue.from_user(request.user)},
                action_url=reverse("accounts:network_invitations"),
            )
            notification_sent = True
        except Exception:
            logger.exception(
                "Failed to send follow notification from user %s to user %s",
                request.user.id,
                target_user.id,
            )
    return JsonResponse(
        {
            "ok": True,
            "is_following": True,
            "created": created,
            "notification_sent": notification_sent,
            "followers_count": Follow.objects.filter(following=target_user).count(),
            "following_count": Follow.objects.filter(follower=target_user).count(),
        }
    )


@login_required
@require_POST
def unfollow_user(request: Any, user_id: str) -> Any:
    target_user = get_object_or_404(User, pk=user_id)
    if request.user == target_user:
        return JsonResponse(
            {"ok": False, "error": _("You cannot unfollow yourself.")},
            status=400,
        )

    deleted, _ = Follow.objects.filter(
        follower=request.user,
        following=target_user,
    ).delete()
    return JsonResponse(
        {
            "ok": True,
            "is_following": False,
            "deleted": bool(deleted),
            "followers_count": Follow.objects.filter(following=target_user).count(),
            "following_count": Follow.objects.filter(follower=target_user).count(),
        }
    )


class InviteToProjectView(LoginRequiredMixin, View):
    def post(self, request, pk):
        user_to_invite = get_object_or_404(get_user_model(), pk=pk)
        project_id = request.POST.get("project_id")
        project = get_object_or_404(Project, pk=project_id, coordinator=request.user)

        # Vérifier que l'utilisateur n'est pas déjà membre ou invité
        if not ProjectMember.objects.filter(
            project=project, member=user_to_invite
        ).exists():
            ProjectMember.objects.create(
                project=project, member=user_to_invite, role="member", status="pending"
            )

            # Notification d’invitation
            NotificationService.create_notification(
                recipient=user_to_invite,
                notification_type="PROJECT_INVITE",
                title=_("Project Invitation"),
                message=_(
                    "You have been invited to join the project '%(project)s' by %(user)s."
                ),
                project_id=project.pk,
                sender_id=request.user.id,
                message_kwargs={
                    "project": project.title,
                    "user": getattr(request.user, "full_name", str(request.user)),
                },
            )

            messages.success(
                request,
                _("Invitation sent to %(name)s.")
                % {"name": getattr(user_to_invite, "full_name", str(user_to_invite))},
            )
        else:
            messages.warning(
                request,
                _("%(name)s is already a member or has a pending invitation.")
                % {"name": getattr(user_to_invite, "full_name", str(user_to_invite))},
            )
        return redirect("accounts:profile", pk=pk)


# --------------------------
# Vue réponse à une invitation
# --------------------------
class RespondToProjectInviteView(LoginRequiredMixin, View):
    def post(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        member = ProjectMember.objects.filter(
            project=project, member=request.user, status="pending"
        ).first()

        if not member:
            messages.error(request, _("No pending invitation for this project."))
            return redirect("projects:project_detail", pk=project_id)

        response = request.POST.get("response")
        notification_id = request.POST.get("notification_id")

        notification = None
        if notification_id:
            try:
                notification = Notification.objects.get(
                    id=notification_id, recipient=request.user
                )
            except Notification.DoesNotExist:
                pass

        if response == "accept":
            member.status = "accepted"
            member.save()

            if notification:
                notification.response_given = True
                notification.response = "accept"
                notification.response_date = timezone.now()
                notification.save()

            NotificationService.create_notification(
                recipient=project.coordinator,
                notification_type="PROJECT_INVITE_ACCEPTED",
                title=_("Invitation Accepted"),
                message=_(
                    "%(user)s has accepted the invitation to join the project '%(project)s'."
                ),
                project_id=project.pk,
                sender_id=request.user.id,
                message_kwargs={
                    "user": getattr(request.user, "full_name", str(request.user)),
                    "project": project.title,
                },
            )
            messages.success(
                request,
                _("You have joined the project '%(project)s'.")
                % {"project": project.title},
            )

        elif response == "reject":
            member.status = "rejected"
            member.save()

            if notification:
                notification.response_given = True
                notification.response = "reject"
                notification.response_date = timezone.now()
                notification.save()

            NotificationService.create_notification(
                recipient=project.coordinator,
                notification_type="PROJECT_INVITE_REJECTED",
                title=_("Invitation Declined"),
                message=_(
                    "%(user)s has declined the invitation to join the project '%(project)s'."
                ),
                project_id=project.pk,
                sender_id=request.user.id,
                message_kwargs={
                    "user": getattr(request.user, "full_name", str(request.user)),
                    "project": project.title,
                },
            )
            messages.info(request, _("You have declined the invitation."))

        return redirect("projects:project_detail", pk=project_id)


# --------------------------
# Autres vues
# --------------------------
def _trash_model_config(content_type: str):
    from events.models import Event
    from forum.models import Topic
    from projects.models import Project
    from resources.models import Corpus, Course, Document, NLPTool

    mapping = {
        "course": {
            "model": Course,
            "owner_field": "author",
            "extra_check": lambda _obj: True,
        },
        "corpus": {
            "model": Corpus,
            "owner_field": "author",
            "extra_check": lambda _obj: True,
        },
        "tool": {
            "model": NLPTool,
            "owner_field": "author",
            "extra_check": lambda _obj: True,
        },
        "article": {
            "model": Document,
            "owner_field": "author",
            "extra_check": lambda obj: getattr(obj, "document_type", "") == "article",
        },
        "thesis": {
            "model": Document,
            "owner_field": "author",
            "extra_check": lambda obj: getattr(obj, "document_type", "") == "thesis",
        },
        "memoir": {
            "model": Document,
            "owner_field": "author",
            "extra_check": lambda obj: getattr(obj, "document_type", "") == "memoir",
        },
        "project": {
            "model": Project,
            "owner_field": "coordinator",
            "extra_check": lambda _obj: True,
        },
        "event": {
            "model": Event,
            "owner_field": "created_by",
            "extra_check": lambda _obj: True,
        },
        "topic": {
            "model": Topic,
            "owner_field": "creator",
            "extra_check": lambda _obj: True,
        },
    }
    return mapping.get(content_type)


def _collect_user_trash_items(user):
    from events.models import Event
    from forum.models import Topic
    from projects.models import Project
    from resources.models import Corpus, Course, Document, NLPTool

    items = []

    for course in Course.all_objects.filter(author=user, is_deleted=True):
        items.append(
            {
                "pk": str(course.pk),
                "content_type": "course",
                "title": course.get_localized_title() or course.title,
                "deleted_at": course.deleted_at,
            }
        )

    for corpus in Corpus.all_objects.filter(author=user, is_deleted=True):
        items.append(
            {
                "pk": str(corpus.pk),
                "content_type": "corpus",
                "title": corpus.get_localized_title() or corpus.title,
                "deleted_at": corpus.deleted_at,
            }
        )

    for tool in NLPTool.all_objects.filter(author=user, is_deleted=True):
        items.append(
            {
                "pk": str(tool.pk),
                "content_type": "tool",
                "title": tool.get_localized_title() or tool.title,
                "deleted_at": tool.deleted_at,
            }
        )

    for document in Document.all_objects.filter(author=user, is_deleted=True):
        doc_type = document.document_type or "article"
        items.append(
            {
                "pk": str(document.pk),
                "content_type": doc_type,
                "title": document.get_localized_title() or document.title,
                "deleted_at": document.deleted_at,
            }
        )

    for project in Project.all_objects.filter(coordinator=user, is_deleted=True):
        items.append(
            {
                "pk": str(project.pk),
                "content_type": "project",
                "title": project.get_localized_title() or project.title,
                "deleted_at": project.deleted_at,
            }
        )

    for event in Event.all_objects.filter(created_by=user, is_deleted=True):
        items.append(
            {
                "pk": str(event.pk),
                "content_type": "event",
                "title": event.get_localized_title() or event.title,
                "deleted_at": event.deleted_at,
            }
        )

    for topic in Topic.all_objects.filter(creator=user, is_deleted=True):
        items.append(
            {
                "pk": str(topic.pk),
                "content_type": "topic",
                "title": topic.get_localized_title() or topic.title,
                "deleted_at": topic.deleted_at,
            }
        )

    items.sort(
        key=lambda item: item["deleted_at"].timestamp() if item["deleted_at"] else 0,
        reverse=True,
    )
    return items


class TrashBinView(LoginAndVerifiedRequiredMixin, View):
    template_name = "account/trash_bin.html"
    allowed_types = {
        "all",
        "course",
        "corpus",
        "tool",
        "article",
        "thesis",
        "memoir",
        "project",
        "event",
        "topic",
    }

    def get(self, request):
        selected_type = (request.GET.get("type") or "all").strip().lower()
        if selected_type not in self.allowed_types:
            selected_type = "all"

        items = _collect_user_trash_items(request.user)
        if selected_type != "all":
            items = [item for item in items if item["content_type"] == selected_type]

        paginator = Paginator(items, 10)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context = {
            "page": "profile",
            "trash_items": page_obj.object_list,
            "page_obj": page_obj,
            "selected_type": selected_type,
            "allowed_types": sorted(self.allowed_types),
            "total_count": len(items),
        }
        return render(request, self.template_name, context)


@login_required
@require_POST
def trash_restore_item(request: Any, content_type: str, pk: str) -> Any:
    config = _trash_model_config(content_type)
    if not config:
        raise Http404(_("Invalid content type."))

    model = config["model"]
    obj = get_object_or_404(model.all_objects.filter(is_deleted=True), pk=pk)
    owner_field = config["owner_field"]
    extra_check = config["extra_check"]

    if not extra_check(obj):
        raise Http404(_("Item not found in trash."))

    owner_id = getattr(obj, f"{owner_field}_id", None)
    if not (request.user.is_staff or request.user.is_superuser or owner_id == request.user.id):
        raise PermissionDenied

    obj.restore()
    messages.success(request, _("Item restored successfully."))
    return redirect("accounts:trash")


@login_required
@require_POST
def trash_delete_item(request: Any, content_type: str, pk: str) -> Any:
    config = _trash_model_config(content_type)
    if not config:
        raise Http404(_("Invalid content type."))

    model = config["model"]
    obj = get_object_or_404(model.all_objects.filter(is_deleted=True), pk=pk)
    owner_field = config["owner_field"]
    extra_check = config["extra_check"]

    if not extra_check(obj):
        raise Http404(_("Item not found in trash."))

    owner_id = getattr(obj, f"{owner_field}_id", None)
    if not (request.user.is_staff or request.user.is_superuser or owner_id == request.user.id):
        raise PermissionDenied

    obj.hard_delete()
    messages.success(request, _("Item permanently deleted."))
    return redirect("accounts:trash")


def awaiting_verification_view(request):
    return render(request, "awaiting_verification.html")


@login_required
def delete_account(request):
    if request.method == "POST":
        user = request.user
        # Soft delete: anonymize user data instead of hard delete
        user.email = f"deleted_{user.id}@deleted.local"
        user.full_name = ""
        user.full_name_ar = ""
        user.full_name_en = ""
        user.bio = ""
        user.bio_ar = ""
        user.bio_en = ""
        user.avatar = None
        user.linkedin_url = None
        user.twitter_url = None
        user.facebook_url = None
        user.is_active = False
        user.status = "blocked"
        user.set_unusable_password()
        user.save()
        logout(request)
        messages.success(request, _("Votre compte a été supprimé avec succès."))
        return redirect("pages:home")
    return render(request, "accounts/delete_account.html")


def custom_logout(request):
    """
    Custom logout view that shows logout confirmation page
    On POST, clears 2FA session before logging out
    """
    if request.method == "POST":
        # Clear pending 2FA session
        if "pending_2fa_user_id" in request.session:
            del request.session["pending_2fa_user_id"]

        request.session.save()
        logout(request)
        messages.success(request, _("You have been logged out."))
        return redirect("pages:home")

    # GET request - show logout confirmation page
    return render(request, "account/logout.html")
