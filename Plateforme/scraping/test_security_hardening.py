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
    User = get_user_model()
    return User.objects.create_user(  # type: ignore[call-arg]
        email="staff-security@example.com",
        password="password123",
        full_name_en="Staff Security",
        full_name_ar="Staff Security",
        is_staff=True,
    )


@pytest.fixture
def regular_user(db):
    User = get_user_model()
    return User.objects.create_user(  # type: ignore[call-arg]
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
def test_run_scraper_trigger_rate_limit_enforced(client, staff_user):
    cache.clear()
    client.force_login(staff_user)
    url = reverse("scraping:run_scraper", kwargs={"category": "invalid"})

    # First 5 are allowed through throttle and fail with invalid category.
    for _ in range(5):
        response = client.post(url)
        assert response.status_code == 400

    blocked = client.post(url)
    assert blocked.status_code == 429


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
