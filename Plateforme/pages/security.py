from __future__ import annotations

import os
from typing import Any

from django.contrib.auth.models import Group
from django.http import HttpRequest
from django.utils import timezone
from django.utils.html import strip_tags


ROLE_ADMIN = "admin"
ROLE_MODERATOR = "moderator"
ROLE_USER = "user"

PERM_VIEW_DASHBOARD = "view_dashboard"
PERM_MANAGE_USERS = "manage_users"
PERM_MANAGE_PROJECTS = "manage_projects"
PERM_MODERATE_MESSAGES = "moderate_messages"
PERM_MANAGE_REPORTS = "manage_reports"
PERM_VIEW_SECURITY_LOGS = "view_security_logs"
PERM_DELETE_CONTENT = "delete_content"

ROLE_PERMISSIONS: dict[str, set[str]] = {
    ROLE_ADMIN: {
        PERM_VIEW_DASHBOARD,
        PERM_MANAGE_USERS,
        PERM_MANAGE_PROJECTS,
        PERM_MODERATE_MESSAGES,
        PERM_MANAGE_REPORTS,
        PERM_VIEW_SECURITY_LOGS,
        PERM_DELETE_CONTENT,
    },
    ROLE_MODERATOR: {
        PERM_VIEW_DASHBOARD,
        PERM_MODERATE_MESSAGES,
        PERM_MANAGE_REPORTS,
        PERM_VIEW_SECURITY_LOGS,
    },
    ROLE_USER: set(),
}

# Route-level permission mapping for custom admin panel endpoints.
ROUTE_PERMISSION_MAP: dict[str, str] = {
    "admin_dashboard": PERM_VIEW_DASHBOARD,
    "admin_api_stats": PERM_VIEW_DASHBOARD,
    "admin_api_recent_users": PERM_VIEW_DASHBOARD,
    "admin_api_recent_content": PERM_VIEW_DASHBOARD,
    "admin_forum": PERM_MODERATE_MESSAGES,
    "admin_feed": PERM_MODERATE_MESSAGES,
    "admin_feed_approve": PERM_MODERATE_MESSAGES,
    "admin_feed_delete": PERM_MODERATE_MESSAGES,
    "admin_feed_view": PERM_MODERATE_MESSAGES,
    "admin_calls": PERM_MANAGE_REPORTS,
    "admin_contact_list": PERM_MANAGE_REPORTS,
    "admin_contact_detail": PERM_MANAGE_REPORTS,
    "admin_security": PERM_VIEW_SECURITY_LOGS,
    "admin_settings": PERM_VIEW_SECURITY_LOGS,
    "admin_users": PERM_MANAGE_USERS,
    "admin_users_new": PERM_MANAGE_USERS,
    "admin_user_edit": PERM_MANAGE_USERS,
    "admin_user_delete": PERM_MANAGE_USERS,
    "admin_user_activate": PERM_MANAGE_USERS,
    "admin_user_block": PERM_MANAGE_USERS,
    "admin_user_history": PERM_MANAGE_USERS,
    "admin_user_status": PERM_MANAGE_USERS,
    "admin_projects": PERM_MANAGE_PROJECTS,
    "admin_publications": PERM_DELETE_CONTENT,
    "admin_news": PERM_DELETE_CONTENT,
    "admin_news_create": PERM_DELETE_CONTENT,
    "admin_news_edit": PERM_DELETE_CONTENT,
    "admin_publications_api": PERM_DELETE_CONTENT,
    "admin_publications_detail_api": PERM_DELETE_CONTENT,
    "admin_corpora": PERM_DELETE_CONTENT,
    "admin_tools": PERM_DELETE_CONTENT,
    "admin_courses": PERM_DELETE_CONTENT,
    "admin_opportunities": PERM_DELETE_CONTENT,
    "admin_institutions": PERM_DELETE_CONTENT,
    "admin_review_item_api": PERM_DELETE_CONTENT,
    "admin_review_save_api": PERM_DELETE_CONTENT,
    "admin_view_item": PERM_DELETE_CONTENT,
    "admin_approve_item": PERM_DELETE_CONTENT,
    "admin_reject_item": PERM_DELETE_CONTENT,
    "admin_statistics": PERM_VIEW_DASHBOARD,
}

ADMIN_UPLOAD_ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf", ".doc", ".docx", ".txt", ".csv", ".zip"
}
ADMIN_UPLOAD_BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".php", ".js", ".jsp", ".com", ".scr", ".msi", ".ps1", ".jar"
}
ADMIN_UPLOAD_ALLOWED_MIME_PREFIXES = ("image/", "application/pdf", "text/", "application/zip")
ADMIN_UPLOAD_MAX_SIZE = 10 * 1024 * 1024  # 10 MB


def get_user_role(user: Any) -> str:
    if not user or not getattr(user, "is_authenticated", False):
        return ROLE_USER
    if getattr(user, "is_superuser", False):
        return ROLE_ADMIN
    if getattr(user, "is_staff", False):
        if user.groups.filter(name__iexact="moderator").exists():
            return ROLE_MODERATOR
        return ROLE_ADMIN
    if user.groups.filter(name__iexact="moderator").exists():
        return ROLE_MODERATOR
    return ROLE_USER


def has_admin_permission(user: Any, permission: str) -> bool:
    role = get_user_role(user)
    return permission in ROLE_PERMISSIONS.get(role, set())


def permission_for_route(url_name: str) -> str:
    return ROUTE_PERMISSION_MAP.get(url_name, PERM_DELETE_CONTENT)


def sanitize_admin_text(value: Any, *, max_len: int = 500) -> str:
    clean = strip_tags(str(value or "")).strip()
    if len(clean) > max_len:
        clean = clean[:max_len]
    return clean


def validate_admin_upload(uploaded_file: Any) -> tuple[bool, str]:
    if not uploaded_file:
        return True, ""

    if uploaded_file.size > ADMIN_UPLOAD_MAX_SIZE:
        return False, "File size exceeds 10MB limit."

    ext = os.path.splitext(getattr(uploaded_file, "name", "") or "")[1].lower()
    if ext in ADMIN_UPLOAD_BLOCKED_EXTENSIONS:
        return False, "Blocked file extension."
    if ext and ext not in ADMIN_UPLOAD_ALLOWED_EXTENSIONS:
        return False, "Unsupported file extension."

    content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
    if content_type and not any(
        content_type == prefix or content_type.startswith(prefix) for prefix in ADMIN_UPLOAD_ALLOWED_MIME_PREFIXES
    ):
        return False, "Unsupported MIME type."

    return True, ""


def ensure_moderator_group() -> Group:
    group, _ = Group.objects.get_or_create(name="moderator")
    return group


def log_admin_activity(
    *,
    user: Any,
    action: str,
    request: HttpRequest | None = None,
    target_type: str = "",
    target_id: str = "",
    details: str = "",
) -> None:
    from .models import AdminActivityLog

    if not user or not getattr(user, "is_authenticated", False):
        return

    ip_address = ""
    user_agent = ""
    if request is not None:
        xff = (request.META.get("HTTP_X_FORWARDED_FOR", "") or "").split(",")[0].strip()
        ip_address = xff or (request.META.get("REMOTE_ADDR", "") or "")[:64]
        user_agent = (request.META.get("HTTP_USER_AGENT", "") or "")[:255]

    AdminActivityLog.objects.create(
        admin_user=user,
        role_snapshot=get_user_role(user),
        action=sanitize_admin_text(action, max_len=120),
        path=(request.path if request else "")[:255],
        http_method=(request.method if request else "N/A")[:10],
        target_type=sanitize_admin_text(target_type, max_len=80),
        target_id=sanitize_admin_text(target_id, max_len=64),
        details=sanitize_admin_text(details, max_len=1000),
        ip_address=ip_address,
        user_agent=user_agent,
        occurred_at=timezone.now(),
    )
