from __future__ import annotations

from django.contrib import admin, messages
from django.utils import timezone


def _has_field(instance, field_name: str) -> bool:
    return hasattr(instance, field_name)


def approve_object(instance, moderator=None, *, save: bool = True):
    """
    Generic moderation transition to approved.

    Supports models with:
    - approval_status
    - approved_by
    - approved_at or approval_date
    - rejection_reason
    - is_approved (legacy)
    """
    updated_fields: list[str] = []

    if _has_field(instance, "approval_status"):
        instance.approval_status = "approved"
        updated_fields.append("approval_status")

    if _has_field(instance, "approved_by") and moderator is not None:
        instance.approved_by = moderator
        updated_fields.append("approved_by")

    approved_time_field = None
    if _has_field(instance, "approved_at"):
        approved_time_field = "approved_at"
    elif _has_field(instance, "approval_date"):
        approved_time_field = "approval_date"
    if approved_time_field:
        setattr(instance, approved_time_field, timezone.now())
        updated_fields.append(approved_time_field)

    if _has_field(instance, "rejection_reason"):
        instance.rejection_reason = ""
        updated_fields.append("rejection_reason")

    if _has_field(instance, "is_approved"):
        instance.is_approved = True
        updated_fields.append("is_approved")

    if save and updated_fields:
        instance.save(update_fields=list(dict.fromkeys(updated_fields)))

    return instance, list(dict.fromkeys(updated_fields))


def reject_object(instance, moderator=None, rejection_reason: str = "", *, save: bool = True):
    """
    Generic moderation transition to rejected.
    """
    updated_fields: list[str] = []

    if _has_field(instance, "approval_status"):
        instance.approval_status = "rejected"
        updated_fields.append("approval_status")

    if _has_field(instance, "rejection_reason"):
        instance.rejection_reason = (rejection_reason or "").strip()
        updated_fields.append("rejection_reason")

    if _has_field(instance, "is_approved"):
        instance.is_approved = False
        updated_fields.append("is_approved")

    # Keep compatibility with models that track approver identity.
    if _has_field(instance, "approved_by") and moderator is not None:
        instance.approved_by = moderator
        updated_fields.append("approved_by")

    if save and updated_fields:
        instance.save(update_fields=list(dict.fromkeys(updated_fields)))

    return instance, list(dict.fromkeys(updated_fields))


class ModerationMixin:
    """
    Reusable admin mixin for approve/reject actions.

    Can be mixed into any ModelAdmin whose model includes moderation fields.
    """

    actions = ("approve_selected", "reject_selected")
    moderation_label_attr = "title"

    def _object_label(self, obj) -> str:
        for attr in (self.moderation_label_attr, "name", "slug", "id"):
            value = getattr(obj, attr, None)
            if value:
                return str(value)
        return str(obj)

    @admin.action(description="Approve selected items")
    def approve_selected(self, request, queryset):
        count = 0
        for obj in queryset:
            _, fields = approve_object(obj, moderator=request.user, save=True)
            if fields:
                count += 1
        self.message_user(
            request,
            f"{count} item(s) approved.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Reject selected items")
    def reject_selected(self, request, queryset):
        count = 0
        for obj in queryset:
            _, fields = reject_object(obj, moderator=request.user, save=True)
            if fields:
                count += 1
        self.message_user(
            request,
            f"{count} item(s) rejected.",
            level=messages.WARNING,
        )
