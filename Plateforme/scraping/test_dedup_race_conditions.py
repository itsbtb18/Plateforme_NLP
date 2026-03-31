from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pytest
from django.db import connection
from feed.models import Post

from scraping.scrapers.base import BaseScraper


class DummyScraper(BaseScraper):
    name = "Dummy Dedup"
    category = "news"

    def scrape(self):
        return []


@pytest.mark.django_db
def test_concurrent_same_url_inserts_only_once(user):
    if connection.vendor == "sqlite":
        pytest.skip("SQLite does not support this threaded write race reliably")

    scraper = DummyScraper()
    source_url = "https://example.com/paper-1"
    create_lock = Lock()

    def worker(i: int):
        item = {"title_en": f"Title {i}", "source_url": source_url}
        is_dup, _reason, _score = scraper._dedup_news(item)
        if is_dup:
            return True

        with create_lock:
            recheck_dup, _r2, _s2 = scraper._dedup_news(item)
            if recheck_dup:
                return True
            Post.objects.create(
                author=user,
                title="Paper",
                title_en="Paper",
                content="Body",
                content_en="Body",
                source_url=source_url,
                source_name="test",
                news_category="paper",
            )
            return False

    with ThreadPoolExecutor(max_workers=10) as pool:
        duplicate_flags = list(pool.map(worker, range(10)))

    assert Post.objects.filter(source_url=source_url).count() == 1
    assert sum(1 for v in duplicate_flags if v) == 9


@pytest.mark.django_db
def test_dedup_handles_missing_url_gracefully():
    scraper = DummyScraper()

    is_dup, reason, score = scraper._dedup_news({"title_en": "No URL item"})

    assert is_dup is False
    assert reason == ""
    assert score == 0.0


@pytest.mark.django_db
def test_semantic_dedup_fallback_on_exact_fail(monkeypatch):
    scraper = DummyScraper()

    class _DupMeta:
        id = "dup-meta-id"
        item_id = "existing-item-id"

    monkeypatch.setattr(
        "scraping.embeddings.find_semantic_duplicate",
        lambda *a, **k: _DupMeta(),
    )

    is_dup, reason, score = scraper._check_duplicate_policy(
        "news",
        {
            "title_en": "A very similar paper title",
            "source_url": "https://novel.example/item",
        },
    )

    assert is_dup is True
    assert "semantic fallback" in reason
    assert score >= 0.88
