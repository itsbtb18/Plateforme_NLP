from django.core.management import call_command

from scraping.models import ScrapingSource


def test_seed_scraping_sources_populates_empty_table(db):
    ScrapingSource.objects.all().delete()

    call_command("seed_scraping_sources")

    assert ScrapingSource.objects.exists()
    categories = set(
        ScrapingSource.objects.values_list("category", flat=True).distinct()
    )
    canonical_categories = {
        "events",
        "tools",
        "courses",
        "news",
        "opportunities",
        "corpus",
    }
    assert categories.issubset(canonical_categories)
    assert "institutions" not in categories
    assert "opportunities" in categories


def test_seed_scraping_sources_skips_when_not_empty(db):
    ScrapingSource.objects.create(
        name="Existing",
        category="events",
        url="https://example.com",
        base_url="https://example.com",
        is_active=True,
    )

    before = ScrapingSource.objects.count()
    call_command("seed_scraping_sources")
    after = ScrapingSource.objects.count()

    assert after == before
