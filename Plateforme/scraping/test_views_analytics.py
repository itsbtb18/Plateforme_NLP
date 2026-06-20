import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone


@pytest.fixture
def test_user(db):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="testuser@example.com",
        password="password",
        full_name_en="Test User",
        full_name_ar="Test User",
    )
    return user


@pytest.fixture
def staff_user(db):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="staffuser@example.com",
        password="password",
        full_name_en="Staff User",
        full_name_ar="Staff User",
        is_staff=True,
    )
    return user


@pytest.mark.django_db
class TestProvenanceViews:
    @pytest.mark.django_db
    def test_duplicates_preview_with_match_score(self, client, staff_user):
        """Test 1: ScrapedItemMeta with match_score=0.92 returns confidence=92.0"""
        from scraping.models import ScrapedItemMeta

        client.force_login(staff_user)
        ScrapedItemMeta.objects.create(
            category="news",
            item_title="Test Item 1",
            skip_reason="dedup_similarity",
            was_skipped=True,
            match_score=0.92,
            source_name="arXiv",
            created_at=timezone.now(),
        )

        url = reverse("scraping:duplicates_preview")
        response = client.get(f"{url}?category=news")

        assert response.status_code == 200
        data = response.json()
        duplicates = data.get("duplicates", [])
        assert len(duplicates) == 1
        assert duplicates[0]["match_confidence"] == 92.0
        assert duplicates[0]["source_name"] == "arXiv"

    @pytest.mark.django_db
    def test_duplicates_preview_fallback_map(self, client, staff_user):
        """Test 2: ScrapedItemMeta without match_score uses fallback map."""
        from scraping.models import ScrapedItemMeta

        client.force_login(staff_user)
        ScrapedItemMeta.objects.create(
            category="events",
            item_title="Old Event",
            skip_reason="dedup_url",
            was_skipped=True,
            match_score=None,  # Old record scenario
            created_at=timezone.now(),
        )

        url = reverse("scraping:duplicates_preview")
        response = client.get(f"{url}?category=events")

        assert response.status_code == 200
        data = response.json()
        duplicates = data.get("duplicates", [])
        assert len(duplicates) == 1
        assert duplicates[0]["match_confidence"] == 100.0  # From fallback map for dedup_url
        assert duplicates[0]["source_name"] == "Unknown"

    @pytest.mark.django_db
    def test_analytics_skip_by_source(self, client, staff_user):
        """Test 3: Multiple metas grouping returns skip_by_source correctly."""
        from scraping.models import ScrapedItemMeta

        client.force_login(staff_user)
        # Create 3 arXiv skipped records and 1 WikiCFP
        for i in range(3):
            ScrapedItemMeta.objects.create(
                category="news",
                item_title=f"Arxiv {i}",
                skip_reason="dedup_similarity",
                was_skipped=True,
                source_name="arXiv",
            )
        ScrapedItemMeta.objects.create(
            category="news",
            item_title="Wiki CFP News",
            skip_reason="dedup_url",
            was_skipped=True,
            source_name="WikiCFP",
        )

        url = reverse("scraping:analytics")
        response = client.get(url)

        assert response.status_code == 200
        data = response.json()

        # Verify arXiv has exactly 3 skips
        skip_by_source = data["by_category"]["news"]["skip_by_source"]
        arxiv_record = next(
            (item for item in skip_by_source if item["source"] == "arXiv"), None
        )
        assert arxiv_record is not None
        assert arxiv_record["count"] == 3

        wiki_record = next(
            (item for item in skip_by_source if item["source"] == "WikiCFP"), None
        )
        assert wiki_record is not None
        assert wiki_record["count"] == 1

    def test_unauthenticated_request(self, client):
        """Test 4: Unauthenticated request redirects to login."""
        url = reverse("scraping:analytics")
        response = client.get(url)

        assert response.status_code == 302
        assert "/login" in response.url

    def test_non_staff_authenticated_request(self, client, test_user):
        """Test 5: Non-staff authenticated request is redirected to login."""
        client.force_login(test_user)
        url = reverse("scraping:analytics")
        response = client.get(url)

        assert response.status_code == 302
        assert "/login" in response.url
