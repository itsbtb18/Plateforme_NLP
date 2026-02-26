"""
Qdrant filter builders — reusable filter construction helpers.

Centralises filter building so search methods don't duplicate
FieldCondition boilerplate.
"""

from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny
from typing import List, Optional


def _conditions_to_filter(conditions: List[FieldCondition]) -> Optional[Filter]:
    """Return a Filter if there are conditions, else None."""
    return Filter(must=conditions) if conditions else None


def build_language_filter(
    language: str,
    extra: Optional[List[FieldCondition]] = None,
) -> Filter:
    """Filter by language, with optional extra conditions."""
    conds = list(extra or [])
    conds.append(FieldCondition(key="language", match=MatchValue(value=language)))
    return Filter(must=conds)


def build_legal_filter(
    jurisdiction: Optional[str] = None,
    category: Optional[str] = None,
    language: Optional[str] = None,
) -> Optional[Filter]:
    """Build filter for legal document search."""
    conditions: List[FieldCondition] = []
    if jurisdiction:
        conditions.append(
            FieldCondition(key="jurisdiction", match=MatchValue(value=jurisdiction))
        )
    if category:
        conditions.append(
            FieldCondition(key="category", match=MatchValue(value=category))
        )
    if language:
        conditions.append(
            FieldCondition(key="language", match=MatchValue(value=language))
        )
    return _conditions_to_filter(conditions)


def build_user_doc_filter(
    session_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    document_id: Optional[int] = None,
    document_ids: Optional[List[int]] = None,
) -> Filter:
    """Build filter for user-uploaded document chunk search.

    When *owner_id* is available, it becomes the primary filter so
    documents are accessible across sessions.  Falls back to
    *session_id* for anonymous users.

    *document_ids* (list) takes precedence over *document_id* (single).
    """
    conditions: List[FieldCondition] = []
    if owner_id:
        conditions.append(
            FieldCondition(key="owner_id", match=MatchValue(value=owner_id))
        )
    elif session_id:
        conditions.append(
            FieldCondition(key="session_id", match=MatchValue(value=session_id))
        )
    if document_ids:
        conditions.append(
            FieldCondition(key="document_id", match=MatchAny(any=document_ids))
        )
    elif document_id:
        conditions.append(
            FieldCondition(key="document_id", match=MatchValue(value=document_id))
        )
    return Filter(must=conditions)


def build_resource_filter(
    resource_type: Optional[str] = None,
) -> Optional[Filter]:
    """Build filter for resource search."""
    if not resource_type:
        return None
    return Filter(
        must=[FieldCondition(key="type", match=MatchValue(value=resource_type))]
    )
