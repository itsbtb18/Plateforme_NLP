import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from scraping.models import SearchQuery

pytestmark = pytest.mark.django_db


def _make_staff_user():
    user_model = get_user_model()
    return user_model.objects.create_user(
        email="prompt-admin@example.com",
        password="password123",
        full_name_en="Prompt Admin",
        full_name_ar="مدير الأوامر",
        is_staff=True,
        is_superuser=True,
    )


def test_category_dashboard_renders_prompt_controls(client):
    client.force_login(_make_staff_user())

    SearchQuery.objects.create(
        category="events",
        query_text="Arabic NLP conferences",
        is_active=True,
    )

    response = client.get(reverse("scraping:category_dashboard", args=["events"]))

    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "AI Prompts" in html
    assert "Add prompt" in html
    assert "catPromptComposer" in html
    assert "data-delete-url" in html


def test_add_prompt_api_creates_prompt(client):
    client.force_login(_make_staff_user())

    response = client.post(
        reverse("scraping:add_prompt_api"),
        data='{"category":"events","query_text":"MENA NLP meetups","is_active":true}',
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["category"] == "events"
    assert payload["query_text"] == "MENA NLP meetups"
    assert payload["is_active"] is True
    assert SearchQuery.objects.filter(
        category="events", query_text="MENA NLP meetups"
    ).exists()


def test_delete_prompt_api_soft_deletes_prompt(client):
    client.force_login(_make_staff_user())

    prompt = SearchQuery.objects.create(
        category="events",
        query_text="Temporary prompt",
        is_active=True,
    )

    response = client.post(
        reverse("scraping:delete_prompt_api", args=[prompt.id]),
        data="{}",
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["deleted"] is True

    prompt.refresh_from_db()
    assert prompt.is_active is False


def test_deleted_prompt_is_not_recreated_on_dashboard_seed(client):
    client.force_login(_make_staff_user())

    prompt = SearchQuery.objects.create(
        category="events",
        query_text="upcoming Arabic NLP conferences",
        is_active=False,
    )

    response = client.get(reverse("scraping:category_dashboard", args=["events"]))

    assert response.status_code == 200
    prompt.refresh_from_db()
    assert prompt.is_active is False
