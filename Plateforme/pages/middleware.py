from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .security import (
    has_admin_permission,
    log_admin_activity,
    permission_for_route,
    validate_admin_upload,
)
from .models import SecurityLog


class AdminPanelSecurityMiddleware:
    """
    Harden custom admin panel endpoints (pages:admin_*) with:
    - authentication gate
    - RBAC permission checks
    - upload validation
    - lightweight activity logging
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = getattr(request, "resolver_match", None)
        if not match:
            return None
        if match.namespace != "pages":
            return None

        url_name = match.url_name or ""
        if not url_name.startswith("admin_"):
            return None

        if not request.user.is_authenticated:
            login_url = reverse("accounts:account_login")
            return redirect(f"{login_url}?next={request.path}")

        required_permission = permission_for_route(url_name)
        if not has_admin_permission(request.user, required_permission):
            messages.error(request, _("Unauthorized access to admin panel."))
            return redirect("pages:home")

        if request.method in {"POST", "PUT", "PATCH"} and request.FILES:
            for uploaded_file in request.FILES.values():
                ok, error = validate_admin_upload(uploaded_file)
                if not ok:
                    log_admin_activity(
                        user=request.user,
                        request=request,
                        action="blocked_upload",
                        details=error,
                    )
                    SecurityLog.objects.create(
                        user=request.user,
                        role=self._get_role(request.user) if hasattr(self, "_get_role") else ("superuser" if request.user.is_superuser else ("staff" if request.user.is_staff else "member")),
                        action="blocked_upload",
                        method=(request.method or "POST").upper(),
                        ip_address=(request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")),
                        path=request.path[:255],
                    )
                    messages.error(request, _("Blocked upload: %(reason)s") % {"reason": error})
                    referer = request.META.get("HTTP_REFERER", "")
                    return redirect(referer or "pages:admin_security")

        request._admin_route_name = url_name  # type: ignore[attr-defined]
        request._admin_required_permission = required_permission  # type: ignore[attr-defined]
        return None

    def process_response(self, request, response):
        route_name = getattr(request, "_admin_route_name", "")
        if not route_name:
            return response

        if getattr(request, "user", None) and request.user.is_authenticated and response.status_code < 500:
            should_log = request.method in {"POST", "PUT", "PATCH", "DELETE"} or route_name in {
                "admin_dashboard",
                "admin_security",
            }
            if should_log:
                log_admin_activity(
                    user=request.user,
                    request=request,
                    action=f"admin_route:{route_name}",
                    target_type="route",
                    target_id=route_name,
                    details=f"status={response.status_code}",
                )
        return response


class SecurityLogMiddleware:
    """
    Global security log middleware for important actions:
    login, upload, create, update, delete.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._log_security_event(request, response)
        return response

    def _get_role(self, user):
        if not user or not user.is_authenticated:
            return 'anonymous'
        if user.is_superuser:
            return 'superuser'
        if user.is_staff:
            return 'staff'
        return 'member'

    def _infer_action(self, request, response):
        path = (request.path or '').lower()
        method = (request.method or 'GET').upper()

        if method == 'POST' and 'login' in path and response.status_code in {200, 302}:
            return 'login'
        if method in {'POST', 'PUT', 'PATCH'} and request.FILES:
            # Heuristic: blocked uploads usually end with 4xx.
            return 'blocked_upload' if response.status_code >= 400 else 'upload'
        if method == 'DELETE' or '/delete/' in path:
            return 'delete'
        if method in {'PUT', 'PATCH'} or '/update/' in path or '/edit/' in path:
            return 'update'
        if method == 'POST' and '/new/' in path:
            return 'create'
        return None

    def _log_security_event(self, request, response):
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return
        action = self._infer_action(request, response)
        if not action:
            return
        user = request.user if getattr(request, 'user', None) and request.user.is_authenticated else None
        SecurityLog.objects.create(
            user=user,
            role=self._get_role(user),
            action=action,
            method=(request.method or 'GET').upper(),
            ip_address=(request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR', '')),
            path=request.path[:255],
        )
