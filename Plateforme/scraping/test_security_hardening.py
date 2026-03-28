# pyright: reportMissingImports=false

import importlib.util
import uuid
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse


@pytest.fixture
def staff_user(db):
    user_model = get_user_model()
    return user_model.objects.create_user(  # type: ignore[call-arg]
        email="staff-security@example.com",
        password="password123",
        full_name_en="Staff Security",
        full_name_ar="Staff Security",
        is_staff=True,
    )


@pytest.fixture
def regular_user(db):
    user_model = get_user_model()
    return user_model.objects.create_user(  # type: ignore[call-arg]
        email="user-security@example.com",
        password="password123",
        full_name_en="Regular User",
        full_name_ar="Regular User",
        is_staff=False,
    )


@pytest.mark.django_db
def test_metrics_unauthenticated_forbidden(client):
    cache.clear()
    url = reverse("scraping:metrics")

    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_metrics_non_staff_forbidden(client, regular_user):
    cache.clear()
    client.force_login(regular_user)
    url = reverse("scraping:metrics")

    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_metrics_rate_limit_enforced(client, staff_user):
    cache.clear()
    client.force_login(staff_user)
    url = reverse("scraping:metrics")

    for _ in range(10):
        response = client.get(url)
        assert response.status_code == 200

    blocked = client.get(url)
    assert blocked.status_code == 429


@pytest.mark.django_db
def test_run_scraper_trigger_has_no_hourly_limit(client, staff_user):
    cache.clear()
    client.force_login(staff_user)
    url = reverse("scraping:run_scraper", kwargs={"category": "invalid"})

    # Invalid category should consistently return 400 without trigger throttling.
    for _ in range(8):
        response = client.post(url)
        assert response.status_code == 400


def _load_settings_module(settings_path: Path):
    module_name = f"security_settings_check_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, str(settings_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to build module spec for settings")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_production_wildcard_allowed_hosts_raises(monkeypatch):
    settings_path = Path(__file__).resolve().parents[1] / "Plateforme" / "settings.py"

    monkeypatch.setenv("DJANGO_DEBUG", "False")
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "localhost,*")
    monkeypatch.setenv("SECRET_KEY", "not-default-secret")

    with pytest.raises(ImproperlyConfigured):
        _load_settings_module(settings_path)


@pytest.fixture
def staff_user2(db):
    user_model = get_user_model()
    return user_model.objects.create_user(  # type: ignore[call-arg]
        email="staff2-security@example.com",
        password="password123",
        full_name_en="Staff Security 2",
        full_name_ar="Staff Security 2",
        is_staff=True,
    )


@pytest.mark.django_db
def test_analytics_rate_limit(client, staff_user):
    """Test 1: Call analytics endpoint 31 times as staff user -> 31st call returns 429 with correct JSON body"""
    cache.clear()
    client.force_login(staff_user)
    url = reverse("scraping:analytics")

    # 30 allowed calls
    for _ in range(30):
        response = client.get(url)
        assert response.status_code == 200

    # 31st call should be rate limited
    response = client.get(url)
    assert response.status_code == 429
    data = response.json()
    assert data["error"] == "rate_limit_exceeded"


@pytest.mark.django_db
def test_polling_rate_limit(client, staff_user):
    """Test 2: Call polling endpoint 61 times -> 61st returns 429"""
    cache.clear()
    client.force_login(staff_user)
    dummy_run_id = str(uuid.uuid4())
    url = reverse("scraping:run_scraper_status", args=[dummy_run_id])

    # 60 allowed calls
    for _ in range(60):
        response = client.get(url)
        assert response.status_code in [200, 404]  # 404 is fine as long as not 429

    # 61st call should be rate limited
    response = client.get(url)
    assert response.status_code == 429
    data = response.json()
    assert data["error"] == "rate_limit_exceeded"


@pytest.mark.django_db
def test_separate_user_buckets(client, staff_user, staff_user2):
    """Test 3: Two different staff users each make 30 analytics calls -> Neither gets 429"""
    cache.clear()
    url = reverse("scraping:analytics")

    # User 1 makes 30 calls
    client.force_login(staff_user)
    for _ in range(30):
        response = client.get(url)
        assert response.status_code == 200

    client.logout()

    # User 2 makes 30 calls
    client.force_login(staff_user2)
    for _ in range(30):
        response = client.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
def test_retry_after_header(client, staff_user):
    """Test 4: 429 response has Retry-After header"""
    cache.clear()
    client.force_login(staff_user)
    url = reverse("scraping:analytics")

    for _ in range(30):
        client.get(url)

    response = client.get(url)
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert response.headers["Retry-After"] == "60"


@pytest.mark.django_db
def test_json_structure(client, staff_user):
    """Test 5: 429 response JSON has error, message, retry_after keys"""
    cache.clear()
    client.force_login(staff_user)
    url = reverse("scraping:analytics")

    for _ in range(30):
        client.get(url)

    response = client.get(url)
    assert response.status_code == 429

    data = response.json()
    assert "error" in data
    assert "message" in data
    assert "retry_after" in data
    assert data["error"] == "rate_limit_exceeded"
    assert data["retry_after"] == 60
    assert data["message"] == "Max 30 requests per 60s exceeded."
