# ruff: noqa: I001

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from QA.models import Post
from scraping.models import ScrapedItemMeta, ScrapingRun


@pytest.fixture
def staff_user(db):
    user_model = get_user_model()
    return user_model.objects.create_user(
        email="results_staff@example.com",
        password="password",
        full_name_en="Results Staff",
        full_name_ar="Results Staff",
        is_staff=True,
    )


@pytest.fixture
def non_staff_user(db):
    user_model = get_user_model()
    return user_model.objects.create_user(
        email="results_user@example.com",
        password="password",
        full_name_en="Regular User",
        full_name_ar="Regular User",
        is_staff=False,
    )


@pytest.mark.django_db
def test_scraping_results_requires_staff(client, non_staff_user):
    client.force_login(non_staff_user)

    response = client.get(reverse("scraping:scraping_results"))

    assert response.status_code == 302


@pytest.mark.django_db
def test_scraping_results_lists_pending_news_with_confidence(client, staff_user):
    client.force_login(staff_user)

    post = Post.objects.create(
        author=staff_user,
        title="Arabic NLP Paper",
        content="content",
        source_url="https://example.org/paper",
        source_name="Example Source",
        approval_status="pending",
    )

    ScrapedItemMeta.objects.create(
        category="news",
        item_title=post.title,
        item_id=str(post.id),
        source_url=post.source_url,
        relevance_score=88.6,
    )

    response = client.get(reverse("scraping:scraping_results"))

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Arabic NLP Paper" in content
    assert "88.6" in content
    assert "PENDING" in content


@pytest.mark.django_db
def test_scraping_results_search_by_title(client, staff_user):
    client.force_login(staff_user)

    Post.objects.create(
        author=staff_user,
        title="Neural Parsing",
        content="content",
        source_url="https://example.org/neural",
        approval_status="pending",
    )
    Post.objects.create(
        author=staff_user,
        title="Machine Translation",
        content="content",
        source_url="https://example.org/mt",
        approval_status="pending",
    )

    url = reverse("scraping:scraping_results")
    response = client.get(f"{url}?q=Neural")

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Neural Parsing" in content
    assert "Machine Translation" not in content


@pytest.mark.django_db
def test_bulk_validate_selected(client, staff_user):
    client.force_login(staff_user)

    post = Post.objects.create(
        author=staff_user,
        title="Pending Validation",
        content="content",
        source_url="https://example.org/validate",
        approval_status="pending",
    )

    response = client.post(
        reverse("scraping:scraping_results"),
        data={
            "action": "validate",
            "selected_items": [f"news:{post.id}"],
        },
    )

    assert response.status_code == 302
    post.refresh_from_db()
    assert post.approval_status == "approved"


@pytest.mark.django_db
def test_bulk_delete_selected(client, staff_user):
    client.force_login(staff_user)

    post = Post.objects.create(
        author=staff_user,
        title="To Delete",
        content="content",
        source_url="https://example.org/delete",
        approval_status="pending",
    )

    response = client.post(
        reverse("scraping:scraping_results"),
        data={
            "action": "delete",
            "selected_items": [f"news:{post.id}"],
        },
    )

    assert response.status_code == 302
    assert not Post.objects.filter(pk=post.pk).exists()


@pytest.mark.django_db
def test_scraping_result_detail_page(client, staff_user):
    client.force_login(staff_user)

    post = Post.objects.create(
        author=staff_user,
        title="Detail View Post",
        content="Detailed content",
        source_url="https://example.org/detail",
        source_name="Detail Source",
        approval_status="pending",
    )

    ScrapedItemMeta.objects.create(
        category="news",
        item_title=post.title,
        item_id=str(post.id),
        source_url=post.source_url,
        source_name=post.source_name,
        relevance_score=77.2,
        domain_scores={"arabic_nlp": 0.9, "ner": 0.6},
    )

    url = reverse("scraping:scraping_result_detail", args=[post.id])
    response = client.get(f"{url}?category=news")

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Detail View Post" in content
    assert "Detailed content" in content
    assert "77.2" in content
    assert "arabic_nlp" in content
    assert "https://example.org/detail" in content


@pytest.mark.django_db
def test_detail_validate_publish_action(client, staff_user):
    client.force_login(staff_user)

    post = Post.objects.create(
        author=staff_user,
        title="Publish From Detail",
        content="content",
        source_url="https://example.org/publish-detail",
        approval_status="pending",
    )

    url = reverse("scraping:scraping_result_detail", args=[post.id])
    response = client.post(f"{url}?category=news", data={"action": "validate"})

    assert response.status_code == 302
    post.refresh_from_db()
    assert post.approval_status == "approved"


@pytest.mark.django_db
def test_detail_delete_action(client, staff_user):
    client.force_login(staff_user)

    post = Post.objects.create(
        author=staff_user,
        title="Delete From Detail",
        content="content",
        source_url="https://example.org/delete-detail",
        approval_status="pending",
    )

    url = reverse("scraping:scraping_result_detail", args=[post.id])
    response = client.post(f"{url}?category=news", data={"action": "delete"})

    assert response.status_code == 302
    assert not Post.objects.filter(pk=post.pk).exists()


@pytest.mark.django_db
def test_post_validate_endpoint(client, staff_user):
    client.force_login(staff_user)

    post = Post.objects.create(
        author=staff_user,
        title="Validate Endpoint",
        content="content",
        source_url="https://example.org/validate-endpoint",
        approval_status="pending",
    )

    url = reverse("scraping:scraping_result_validate", args=[post.id])
    response = client.post(url, data={"category": "news"})

    assert response.status_code == 302
    post.refresh_from_db()
    assert post.approval_status == "approved"


@pytest.mark.django_db
def test_post_delete_endpoint(client, staff_user):
    client.force_login(staff_user)

    post = Post.objects.create(
        author=staff_user,
        title="Delete Endpoint",
        content="content",
        source_url="https://example.org/delete-endpoint",
        approval_status="pending",
    )

    url = reverse("scraping:scraping_result_delete", args=[post.id])
    response = client.post(url, data={"category": "news"})

    assert response.status_code == 302
    assert not Post.objects.filter(pk=post.pk).exists()


@pytest.mark.django_db
def test_post_bulk_action_endpoint(client, staff_user):
    client.force_login(staff_user)

    first = Post.objects.create(
        author=staff_user,
        title="Bulk First",
        content="content",
        source_url="https://example.org/bulk-first",
        approval_status="pending",
    )
    second = Post.objects.create(
        author=staff_user,
        title="Bulk Second",
        content="content",
        source_url="https://example.org/bulk-second",
        approval_status="pending",
    )

    url = reverse("scraping:scraping_results_bulk_action")
    response = client.post(
        url,
        data={
            "action": "validate",
            "category": "news",
            "item_ids": [str(first.id), str(second.id)],
        },
    )

    assert response.status_code == 302
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.approval_status == "approved"
    assert second.approval_status == "approved"


@pytest.mark.django_db
def test_scraping_results_run_id_filter(client, staff_user):
    client.force_login(staff_user)

    run = ScrapingRun.objects.create(category="news", status="completed")
    start = timezone.now() - timezone.timedelta(minutes=20)
    end = timezone.now() - timezone.timedelta(minutes=10)
    ScrapingRun.objects.filter(pk=run.pk).update(started_at=start, completed_at=end)
    run.refresh_from_db()

    inside = Post.objects.create(
        author=staff_user,
        title="Inside Run Window",
        content="content",
        source_url="https://example.org/inside",
        approval_status="pending",
    )
    outside = Post.objects.create(
        author=staff_user,
        title="Outside Run Window",
        content="content",
        source_url="https://example.org/outside",
        approval_status="pending",
    )

    Post.objects.filter(pk=inside.pk).update(created_at=end)
    Post.objects.filter(pk=outside.pk).update(created_at=timezone.now())

    url = reverse("scraping:scraping_results")
    response = client.get(f"{url}?run_id={run.pk}")

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Inside Run Window" in content
    assert "Outside Run Window" not in content
