import requests
from django.core.management import call_command

from scraping.models import ScrapingSource
from scraping.scrapers.base import BaseScraper


class DummyScraper(BaseScraper):
    name = "Dummy Source"
    category = "news"

    def scrape(self):
        return None


def test_source_is_quarantined_after_three_failures(db):
    source = ScrapingSource.objects.create(
        name="Dead Source",
        category="news",
        base_url="https://dead.example",
        is_active=True,
    )

    scraper = DummyScraper()

    def raise_conn_error(*args, **kwargs):
        raise requests.exceptions.ConnectionError("dns failed")

    scraper.session.get = raise_conn_error  # type: ignore[method-assign]

    for _ in range(3):
        assert scraper.fetch(source.base_url, source_name=source.name) is None

    source.refresh_from_db()
    assert source.fail_count == 3
    assert source.is_active is False
    assert source.last_error_at is not None


def test_reactivate_sources_command_resets_quarantine_fields(db):
    source = ScrapingSource.objects.create(
        name="Recoverable Source",
        category="news",
        base_url="https://recover.example",
        is_active=False,
        fail_count=5,
        last_error="network failure",
    )

    call_command("reactivate_sources")

    source.refresh_from_db()
    assert source.is_active is True
    assert source.fail_count == 0
    assert source.last_error == ""
