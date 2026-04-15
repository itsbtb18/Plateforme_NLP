import pytest
from django.contrib.auth import get_user_model

from scraping.models import ScrapingSource


@pytest.fixture
def user(transactional_db):
    user_model = get_user_model()
    return user_model.objects.create_user(  # type: ignore[call-arg]
        email="test@test.com",
        password="pass123",  # nosec B106
        full_name_en="Test User",
        full_name_ar="Test User",
    )


@pytest.fixture
def staff_user(db):
    user_model = get_user_model()
    return user_model.objects.create_user(  # type: ignore[call-arg]
        email="staff@test.com",
        password="pass123",  # nosec B106
        full_name_en="Staff User",
        full_name_ar="Staff User",
        is_staff=True,
    )


@pytest.fixture
def scraping_source(db):
    return ScrapingSource.objects.create(
        name="Test Source",
        base_url="https://example.com",
        category="events",
        is_active=True,
    )
