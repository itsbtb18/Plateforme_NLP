"""
Exa budget and safety policy.

Per-session and per-user safeguards:
  - max calls per session (configurable)
  - max calls per user per hour (configurable)
  - cache-first strategy to avoid redundant paid calls

When budget is exceeded:
  - skip Exa
  - continue with existing safe fallback path
  - log reason with structured fields
"""

import logging
import time
from collections import defaultdict
from typing import Dict, Optional, Tuple

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ExaBudgetPolicy:
    """Rate-limit and budget control for Exa API calls."""

    def __init__(self):
        # session_id -> call count
        self._session_calls: Dict[str, int] = {}
        # user_id -> list of (timestamp,) for sliding window
        self._user_calls: Dict[str, list] = defaultdict(list)

    def can_call(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Check if an Exa call is allowed.

        Returns:
            (allowed, reason) — reason is empty if allowed.
        """
        # Check session budget
        if session_id:
            count = self._session_calls.get(session_id, 0)
            if count >= settings.EXA_MAX_CALLS_PER_SESSION:
                reason = (
                    f"session_budget_exceeded: {count}/"
                    f"{settings.EXA_MAX_CALLS_PER_SESSION}"
                )
                logger.warning(
                    "Exa call BLOCKED: %s session=%s",
                    reason, session_id,
                )
                return False, reason

        # Check user hourly budget
        if user_id:
            now = time.time()
            one_hour_ago = now - 3600
            # Clean old entries
            self._user_calls[user_id] = [
                t for t in self._user_calls[user_id] if t > one_hour_ago
            ]
            if len(self._user_calls[user_id]) >= settings.EXA_MAX_CALLS_PER_HOUR:
                reason = (
                    f"user_hourly_budget_exceeded: "
                    f"{len(self._user_calls[user_id])}/"
                    f"{settings.EXA_MAX_CALLS_PER_HOUR}"
                )
                logger.warning(
                    "Exa call BLOCKED: %s user=%s",
                    reason, user_id,
                )
                return False, reason

        return True, ""

    def record_call(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Record that an Exa call was made."""
        if session_id:
            self._session_calls[session_id] = (
                self._session_calls.get(session_id, 0) + 1
            )
        if user_id:
            self._user_calls[user_id].append(time.time())

    def get_usage(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict:
        """Get current usage stats."""
        stats = {}
        if session_id:
            stats["session_calls"] = self._session_calls.get(session_id, 0)
            stats["session_limit"] = settings.EXA_MAX_CALLS_PER_SESSION
        if user_id:
            now = time.time()
            one_hour_ago = now - 3600
            recent = [t for t in self._user_calls.get(user_id, []) if t > one_hour_ago]
            stats["user_hourly_calls"] = len(recent)
            stats["user_hourly_limit"] = settings.EXA_MAX_CALLS_PER_HOUR
        return stats

    def reset_session(self, session_id: str) -> None:
        """Reset session call counter."""
        self._session_calls.pop(session_id, None)


# Singleton
_policy: ExaBudgetPolicy | None = None


def get_exa_policy() -> ExaBudgetPolicy:
    global _policy
    if _policy is None:
        _policy = ExaBudgetPolicy()
    return _policy
