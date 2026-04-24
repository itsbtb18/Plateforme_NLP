import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _make_staff_user():
    user_model = get_user_model()
    return user_model.objects.create_user(
        email="custom-element-admin@example.com",
        password="password123",
        full_name_en="Custom Element Admin",
        full_name_ar="مسؤول العنصر المخصص",
        is_staff=True,
        is_superuser=True,
    )


def test_category_dashboard_renders_custom_element_controls(client):
    client.force_login(_make_staff_user())

    response = client.get(reverse("scraping:category_dashboard", args=["events"]))

    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "Add custom element" in html
    assert "catCustomElementModal" in html
    assert reverse("scraping:run_custom_element", args=["events"]) in html


def test_run_custom_element_returns_success_for_single_item(client, monkeypatch):
    from scraping import views_root

    client.force_login(_make_staff_user())

    monkeypatch.setattr(
        views_root,
        "_build_custom_element_search_row",
        lambda element_url: {
            "title": "Single event page",
            "url": element_url,
            "content": "This page describes a real event page with dates, venue, and registration.",
        },
    )

    class _StubScraper:
        def bind_progress_run(self, _run):
            return None

        def get_active_search_queries(self):
            return ["direct-url"]

        def run(self):
            return {
                "items_found": 1,
                "items_created": 1,
                "items_updated": 0,
                "items_skipped": 0,
                "errors": [],
                "results": [{"title": "Single event page"}],
            }

    monkeypatch.setattr(views_root, "get_scraper", lambda _category: _StubScraper())

    response = client.post(
        reverse("scraping:run_custom_element", args=["events"]),
        data='{"url":"https://example.com/event"}',
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["items_created"] == 1
    assert payload["items_updated"] == 0


def test_run_custom_element_rejects_non_item_pages(client, monkeypatch):
    from scraping import views_root

    client.force_login(_make_staff_user())

    monkeypatch.setattr(
        views_root,
        "_build_custom_element_search_row",
        lambda element_url: {
            "title": "Events listing",
            "url": element_url,
            "content": "Browse all events and browse the archive. This is a listing page.",
        },
    )

    class _StubRejectedScraper:
        def bind_progress_run(self, _run):
            return None

        def get_active_search_queries(self):
            return ["direct-url"]

        def run(self):
            return {
                "items_found": 0,
                "items_created": 0,
                "items_updated": 0,
                "items_skipped": 1,
                "errors": ["not_relevant"],
                "results": [],
            }

    monkeypatch.setattr(
        views_root, "get_scraper", lambda _category: _StubRejectedScraper()
    )

    response = client.post(
        reverse("scraping:run_custom_element", args=["events"]),
        data='{"url":"https://example.com/listing"}',
        content_type="application/json",
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == "error"
    assert "failed validation" in payload["message"].lower()
