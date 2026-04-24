from __future__ import annotations

from typing import Iterable

from django.utils import timezone

from pages.security import ROLE_ADMIN, get_user_role


MODERATION_STATUSES = {"pending", "approved", "rejected"}


def normalize_skills(skills: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for skill in skills or []:
        cleaned = str(skill or "").strip()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned[:80])
    return normalized


def apply_creation_policy(opportunity, *, user) -> str:
    role = get_user_role(user)
    opportunity.user_role = role

    if role == ROLE_ADMIN:
        opportunity.status = "approved"
        opportunity.approval_status = "approved"
        opportunity.is_published = True
        opportunity.approved_by = user
        opportunity.approved_at = timezone.now()
        opportunity.rejection_reason = ""
    else:
        opportunity.status = "pending"
        opportunity.approval_status = "pending"
        opportunity.is_published = False
        opportunity.approved_by = None
        opportunity.approved_at = None
        opportunity.rejection_reason = ""

    return role


def apply_moderation_state(opportunity, *, status: str, moderator=None, rejection_reason: str = ""):
    if status not in MODERATION_STATUSES:
        raise ValueError(f"Unsupported moderation status: {status}")

    opportunity.status = status
    opportunity.approval_status = status
    opportunity.is_published = status == "approved"
    opportunity.rejection_reason = (rejection_reason or "").strip() if status == "rejected" else ""

    if moderator is not None:
        opportunity.approved_by = moderator

    opportunity.approved_at = timezone.now() if status == "approved" else None
    return opportunity
