import pytest

from feed.models import Post
from scraping.models import ScrapedItemMeta
from scraping.scrapers.base import BaseScraper


pytestmark = [pytest.mark.django_db, pytest.mark.integration]


class DummyScraper(BaseScraper):
    source_name = "dummy_source"
    category = "events"

    def scrape(self):
        return []


def test_event_dedup_by_slug_and_date(EventFactory):
    existing = EventFactory(title="NLP Summit", title_en="NLP Summit")
    scraper = DummyScraper()

    incoming = {
        "title": existing.title,
        "title_en": existing.title_en,
        "start_date": existing.start_date,
        "website": existing.website,
    }

    is_dup, reason = scraper._dedup_event(incoming)
    assert is_dup is True
    assert "website_url exact match" in reason


def test_tool_dedup_by_access_link_or_github(NLPToolFactory):
    existing = NLPToolFactory(
        access_link="https://tool.example.org", github_url="https://github.com/org/repo"
    )
    scraper = DummyScraper()

    by_link = {
        "title": "Different",
        "access_link": existing.access_link,
    }
    by_repo = {
        "title": "Different 2",
        "github_url": existing.github_url,
    }

    assert scraper._dedup_tool(by_link)[0] is True
    assert scraper._dedup_tool(by_repo)[0] is True


def test_news_dedup_by_slug_or_source_url(PostFactory):
    existing = PostFactory(slug="breaking-nlp", title="Breaking NLP")
    scraper = DummyScraper()

    by_slug = {"title": existing.title}
    by_url = {
        "title": "Other 2",
        "source_url": "https://news.example.org/item-1",
    }
    Post.objects.filter(id=existing.id).update(
        source_url="https://news.example.org/item-1"
    )

    assert scraper._dedup_news(by_slug)[0] is True
    assert scraper._dedup_news(by_url)[0] is True


def test_course_dedup_by_title_instructor_or_link(CourseFactory):
    existing = CourseFactory(
        title="Intro to NLP",
        description="Course body\nInstructor: Jane Roe",
        access_link="https://courses.example.org/intro-nlp",
    )
    scraper = DummyScraper()

    same_title_and_instructor = {
        "title": existing.title,
        "description": "Fresh text\nInstructor: Jane Roe",
    }
    same_link = {
        "title": "Another",
        "access_link": existing.access_link,
    }

    assert scraper._dedup_course(same_title_and_instructor)[0] is True
    assert scraper._dedup_course(same_link)[0] is True


def test_institution_dedup_by_website_or_ror(InstitutionFactory):
    existing = InstitutionFactory(
        website="https://inst-dup.example.org", ror_id="01234abcd"
    )
    scraper = DummyScraper()

    by_site = {
        "name": "Other institution",
        "website": existing.website,
    }
    by_ror = {
        "name": "Another institution",
        "ror_id": existing.ror_id,
    }

    assert scraper._dedup_institution(by_site)[0] is True
    assert scraper._dedup_institution(by_ror)[0] is True


def test_skip_reason_persisted_on_duplicate(EventFactory):
    existing = EventFactory(title="Persisted Duplicate", title_en="Persisted Duplicate")
    scraper = DummyScraper()

    payload = {
        "title_en": existing.title_en,
        "start_date": existing.start_date,
        "website_url": existing.website,
    }

    duplicate, reason = scraper._check_duplicate_policy("events", payload)

    assert duplicate is True
    assert "match" in reason
    meta = ScrapedItemMeta.objects.get(category="events", item_title=existing.title)
    assert meta.was_skipped is True
    assert meta.skip_reason == "dedup_url"
