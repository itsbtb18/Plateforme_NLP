import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse

from scraping.views_root import _enforce_rate_limit


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


@pytest.fixture
def staff_user(db):
    user_model = get_user_model()
    return user_model.objects.create_user(  # type: ignore[call-arg]
        email="staff-ratelimit@example.com",
        password="password123",
        full_name_en="Rate Limit Staff",
        full_name_ar="Rate Limit Staff",
        is_staff=True,
    )


def test_rate_limit_allows_under_threshold():
    key = "allow_under_threshold"

    results = [_enforce_rate_limit(key, limit=5, window_seconds=60) for _ in range(3)]

    assert results == [True, True, True]


def test_rate_limit_blocks_over_threshold():
    key = "blocks_over_threshold"

    results = [_enforce_rate_limit(key, limit=5, window_seconds=60) for _ in range(6)]

    assert results[:5] == [True, True, True, True, True]
    assert results[5] is False


def test_rate_limit_resets_after_window():
    key = "reset_after_window"

    first_window = [
        _enforce_rate_limit(key, limit=5, window_seconds=60) for _ in range(5)
    ]
    assert first_window == [True, True, True, True, True]

    # Simulate expiration of the sliding window.
    cache.delete(f"rate_limit:{key}")

    assert _enforce_rate_limit(key, limit=5, window_seconds=60) is True


def test_rate_limit_different_keys_independent():
    key_a = "key_A"
    key_b = "key_B"

    for _ in range(5):
        assert _enforce_rate_limit(key_a, limit=5, window_seconds=60) is True

    assert _enforce_rate_limit(key_a, limit=5, window_seconds=60) is False
    assert _enforce_rate_limit(key_b, limit=5, window_seconds=60) is True


@pytest.mark.django_db
def test_rate_limit_returns_429_response(client, staff_user):
    client.force_login(staff_user)
    url = reverse("scraping:analytics")

    for _ in range(30):
        response = client.get(url)
        assert response.status_code == 200

    blocked = client.get(url)
    assert blocked.status_code == 429

    payload = blocked.json()
    assert "retry_after" in payload
    assert payload["error"] == "rate_limit_exceeded"
    assert blocked.headers.get("Retry-After") == "60"
