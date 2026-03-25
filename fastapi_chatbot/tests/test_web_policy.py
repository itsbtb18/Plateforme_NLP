"""Unit tests for Exa budget / rate-limit policy."""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.web.policy import ExaBudgetPolicy


def _make_policy():
    return ExaBudgetPolicy()


# ── Session budget ────────────────────────────────────────────────


def test_allows_call_within_limit():
    policy = _make_policy()
    allowed, reason = policy.can_call(session_id="s1")
    assert allowed is True
    assert reason == ""


def test_blocks_call_when_session_exhausted():
    policy = _make_policy()
    # Record max_calls_per_session = 10 calls
    for _ in range(10):
        policy.record_call(session_id="s2")
    allowed, reason = policy.can_call(session_id="s2")
    assert allowed is False
    assert "session_budget_exceeded" in reason


def test_different_sessions_independent():
    policy = _make_policy()
    for _ in range(10):
        policy.record_call(session_id="s3")
    # s4 should still be allowed
    allowed, _ = policy.can_call(session_id="s4")
    assert allowed is True


# ── User hourly budget ────────────────────────────────────────────


def test_allows_user_within_hourly_limit():
    policy = _make_policy()
    policy.record_call(user_id="u1")
    allowed, _ = policy.can_call(user_id="u1")
    assert allowed is True


def test_blocks_user_when_hourly_exhausted():
    policy = _make_policy()
    for _ in range(30):
        policy.record_call(user_id="u2")
    allowed, reason = policy.can_call(user_id="u2")
    assert allowed is False
    assert "user_hourly_budget_exceeded" in reason


# ── Combined checks ────────────────────────────────────────────


def test_combined_session_and_user():
    policy = _make_policy()
    # Both within limits
    policy.record_call(session_id="s5", user_id="u3")
    allowed, _ = policy.can_call(session_id="s5", user_id="u3")
    assert allowed is True


# ── Usage stats ────────────────────────────────────────────────


def test_usage_stats():
    policy = _make_policy()
    policy.record_call(session_id="s6", user_id="u4")
    policy.record_call(session_id="s6", user_id="u4")
    stats = policy.get_usage(session_id="s6", user_id="u4")
    assert stats["session_calls"] == 2
    assert stats["user_hourly_calls"] == 2


def test_reset_session():
    policy = _make_policy()
    for _ in range(5):
        policy.record_call(session_id="s7")
    policy.reset_session("s7")
    stats = policy.get_usage(session_id="s7")
    assert stats["session_calls"] == 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
