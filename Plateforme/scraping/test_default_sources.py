from django.urls import reverse

from scraping.models import ScrapingSource


def test_list_sources_auto_seeds_defaults_without_duplicates(client, staff_user):
    ScrapingSource.objects.all().delete()
    client.force_login(staff_user)
    url = reverse("scraping:list_custom_sources")

    first = client.get(url)
    assert first.status_code == 200

    first_sources = first.json().get("sources", [])
    assert first_sources

    categories = {src.get("category") for src in first_sources}
    assert categories == {"events", "tools", "news", "courses", "institutions"}

    for source in first_sources:
        assert source.get("name")
        assert source.get("url")

    count_after_first = ScrapingSource.objects.count()

    second = client.get(url)
    assert second.status_code == 200
    assert ScrapingSource.objects.count() == count_after_first
