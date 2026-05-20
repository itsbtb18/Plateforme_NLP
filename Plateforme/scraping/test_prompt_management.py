import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from scraping.constants import CANONICAL_CATEGORIES
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


@pytest.mark.parametrize("category", CANONICAL_CATEGORIES)
def test_delete_prompt_api_hard_deletes_prompt(client, category):
    client.force_login(_make_staff_user())

    prompt = SearchQuery.objects.create(
        category=category,
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

    assert not SearchQuery.objects.filter(pk=prompt.pk).exists()

    dashboard_response = client.get(
        reverse("scraping:category_dashboard", args=[category])
    )
    assert dashboard_response.status_code == 200
    assert "Temporary prompt" not in dashboard_response.content.decode("utf-8")


def test_category_dashboard_renders_all_active_prompts(client):
    client.force_login(_make_staff_user())

    prompt_texts = [f"events prompt {index}" for index in range(1, 13)]
    for text in prompt_texts:
        SearchQuery.objects.create(category="events", query_text=text, is_active=True)

    response = client.get(reverse("scraping:category_dashboard", args=["events"]))

    assert response.status_code == 200
    html = response.content.decode("utf-8")
    for text in prompt_texts:
        assert text in html


def test_category_dashboard_does_not_render_laws_category(client):
    client.force_login(_make_staff_user())

    response = client.get(reverse("scraping:category_dashboard", args=["events"]))

    assert response.status_code == 200
    assert "laws" not in response.content.decode("utf-8").lower()


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


def test_add_prompt_api_rejects_when_category_prompt_limit_reached(client, monkeypatch):
    from scraping import views_root

    monkeypatch.setattr(views_root, "_prompt_limit_for_category", lambda _category: 3)

    client.force_login(_make_staff_user())

    for index in range(1, 4):
        SearchQuery.objects.create(
            category="events",
            query_text=f"events prompt {index}",
            is_active=True,
        )

    response = client.post(
        reverse("scraping:add_prompt_api"),
        data='{"category":"events","query_text":"events prompt extra","is_active":true}',
        content_type="application/json",
    )

    assert response.status_code == 400
    payload = response.json()
    assert "Prompt limit reached" in payload["error"]


def test_category_dashboard_includes_prompt_limit_metadata(client, monkeypatch):
    from scraping import views_root

    monkeypatch.setattr(views_root, "_prompt_limit_for_category", lambda _category: 4)

    client.force_login(_make_staff_user())

    for index in range(1, 3):
        SearchQuery.objects.create(
            category="events",
            query_text=f"existing prompt {index}",
            is_active=True,
        )

    response = client.get(reverse("scraping:category_dashboard", args=["events"]))

    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert 'data-max-prompts="4"' in html
    assert 'data-active-prompts="2"' in html
