from __future__ import annotations

from collections.abc import Sequence

from django.core.exceptions import FieldDoesNotExist
from django.db.models import Q, QuerySet

from .models import Friendship


def blocked_user_ids_for(user) -> set:
    if not getattr(user, "is_authenticated", False):
        return set()

    relations = Friendship.objects.filter(
        Q(requester=user, status=Friendship.Status.BLOCKED)
        | Q(addressee=user, status=Friendship.Status.BLOCKED)
    ).values_list("requester_id", "addressee_id")

    hidden_ids: set = set()
    for requester_id, addressee_id in relations:
        if requester_id == user.id:
            hidden_ids.add(addressee_id)
        else:
            hidden_ids.add(requester_id)
    return hidden_ids


def exclude_hidden_users(queryset: QuerySet, user, fields: Sequence[str]) -> QuerySet:
    hidden_ids = blocked_user_ids_for(user)
    if not hidden_ids:
        return queryset

    q = Q()
    for field in fields:
        try:
            queryset.model._meta.get_field(field)
        except FieldDoesNotExist:
            continue
        q |= Q(**{f"{field}_id__in": hidden_ids})

    if not q.children:
        return queryset
    return queryset.exclude(q)
