# pyright: reportMissingImports=false

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from events.models import Event
from feed.models import Post
from institutions.models import Country, Institution
from resources.models import Course, NLPTool

from scraping.scrapers.base import BaseScraper
from scraping.scrapers.events import EventScraper


class DummyScraper(BaseScraper):
    name = "dummy"
    category = "tests"

    def scrape(self):
        return None


def _check_dup(scraper, category, payload):
    result = scraper._check_duplicate_policy(category, payload)
    return result[0], result[1]


@pytest.fixture
def scraper():
    return DummyScraper()


@pytest.fixture
def user(db):
    user_model = get_user_model()
    return user_model.objects.create_user(  # type: ignore[call-arg]
        email="dedup@example.com",
        password="x",
        full_name_en="Dedup User",
        full_name_ar="مستخدم",
    )


@pytest.fixture
def country(db):
    return Country.objects.create(name_en="Algeria", name_ar="الجزائر", code="DZ")


@pytest.fixture
def institution(db, country, user):
    return Institution.objects.create(
        name="Test University",
        name_en="Test University",
        name_ar="جامعة الاختبار",
        acronym="TU",
        type="University",
        country=country,
        city="Algiers",
        city_en="Algiers",
        city_ar="الجزائر",
        website="https://tu.example.org",
        email="info@tu.example.org",
        address="Algiers",
        address_en="Algiers",
        address_ar="الجزائر",
        description="desc",
        description_en="desc",
        description_ar="desc",
        created_by=user,
        approval_status="approved",
    )


@pytest.mark.django_db
def test_events_dedup_rule_1_website(scraper, institution):
    Event.objects.create(
        title="NLP Summit",
        title_en="NLP Summit",
        description="desc",
        description_en="desc",
        event_type="conference",
        domains="nlp",
        location="Algiers",
        start_date=date(2026, 8, 10),
        end_date=date(2026, 8, 11),
        website="https://event.example.com",
        organizer=institution,
        contact_email="events@example.com",
        created_by=institution.created_by,
    )

    is_dup, reason = _check_dup(
        scraper,
        "events",
        {
            "title_en": "Different title",
            "website_url": "https://event.example.com",
            "organizer": institution,
            "start_date": date(2026, 9, 1),
            "end_date": date(2026, 9, 2),
        },
    )

    assert is_dup is True
    assert "website_url" in reason


@pytest.mark.django_db
def test_events_dedup_rule_2_organizer_date_overlap(scraper, institution):
    Event.objects.create(
        title="Event One",
        title_en="Event One",
        description="desc",
        description_en="desc",
        event_type="conference",
        domains="nlp",
        location="Algiers",
        start_date=date(2026, 10, 10),
        end_date=date(2026, 10, 12),
        website="https://event-1.example.com",
        organizer=institution,
        contact_email="events@example.com",
        created_by=institution.created_by,
    )

    is_dup, reason = _check_dup(
        scraper,
        "events",
        {
            "title_en": "Another title",
            "website_url": "https://new-url.example.com",
            "organizer": institution,
            "start_date": date(2026, 10, 14),
            "end_date": date(2026, 10, 16),
        },
    )

    assert is_dup is True
    assert "overlapping date range" in reason


@pytest.mark.django_db
def test_events_dedup_rule_3_title_similarity(scraper, institution):
    Event.objects.create(
        title="Arabic NLP Conference 2026",
        title_en="Arabic NLP Conference 2026",
        description="desc",
        description_en="desc",
        event_type="conference",
        domains="nlp",
        location="Algiers",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 2),
        website="https://event-title.example.com",
        organizer=institution,
        contact_email="events@example.com",
        created_by=institution.created_by,
    )

    is_dup, reason = _check_dup(
        scraper,
        "events",
        {
            "title_en": "Arabic NLP Conference 2026!",
            "website_url": "https://fresh.example.com",
            "organizer": institution,
            "start_date": date(2026, 12, 1),
            "end_date": date(2026, 12, 2),
        },
    )

    assert is_dup is True
    assert "85%" in reason


@pytest.mark.django_db
def test_event_scrape_duplicate_updates_tracking_fields(institution, monkeypatch):
    existing = Event.objects.create(
        title="Tracking Event",
        title_en="Tracking Event",
        description="old desc",
        description_en="old desc",
        event_type="conference",
        domains="nlp",
        location="Algiers",
        start_date=date(2026, 10, 10),
        end_date=date(2026, 10, 11),
        website="https://tracking.example.com",
        organizer=institution,
        contact_email="events@example.com",
        created_by=institution.created_by,
        last_scraped_at=timezone.now() - timedelta(hours=2),
        update_count=0,
    )

    scraper_instance = EventScraper()
    scraper_instance.name = "Test Event Scraper"
    scraper_instance.source = SimpleNamespace(
        name="Test Source",
        category="events",
        scrape_config={},
    )

    monkeypatch.setattr(
        scraper_instance, "passes_min_confidence_to_save", lambda item: True
    )
    monkeypatch.setattr(
        scraper_instance, "_passes_hard_event_rules", lambda item: (True, "")
    )
    monkeypatch.setattr(scraper_instance, "_ensure_event_fields", lambda item: item)
    monkeypatch.setattr(
        scraper_instance, "_resolve_organizer", lambda item: institution
    )
    monkeypatch.setattr(
        scraper_instance, "get_system_user", lambda: institution.created_by
    )

    scraper_instance._save_event_candidate(
        {
            "title_en": "Tracking Event",
            "description_en": "fresh desc",
            "description": "fresh desc",
            "event_type": "conference",
            "domains": "nlp",
            "location": "Algiers",
            "start_date": "2026-10-10",
            "end_date": "2026-10-11",
            "website": "https://tracking.example.com",
            "source_name": "Test Source",
            "organizer": institution,
            "contact_email": "events@example.com",
        }
    )

    existing.refresh_from_db()

    assert scraper_instance.items_created == 0
    assert scraper_instance.items_updated == 1
    assert existing.update_count == 1
    assert existing.update_counter == 1
    assert existing.last_scraped_at is not None


@pytest.mark.django_db
def test_event_scrape_preserves_approved_status_on_terminal_records(
    institution,
    monkeypatch,
):
    existing = Event.objects.create(
        title="Approved Tracking Event",
        title_en="Approved Tracking Event",
        description="old desc",
        description_en="old desc",
        event_type="conference",
        domains="nlp",
        location="Algiers",
        start_date=date(2026, 10, 10),
        end_date=date(2026, 10, 11),
        website="https://approved-tracking.example.com",
        organizer=institution,
        contact_email="events@example.com",
        created_by=institution.created_by,
        scrape_status="APPROVED",
        confidence_score=0.70,
    )

    scraper_instance = EventScraper()
    scraper_instance.name = "Test Event Scraper"
    scraper_instance.source = SimpleNamespace(
        name="Test Source",
        category="events",
        scrape_config={},
    )

    monkeypatch.setattr(
        scraper_instance, "passes_min_confidence_to_save", lambda item: True
    )
    monkeypatch.setattr(
        scraper_instance, "_passes_hard_event_rules", lambda item: (True, "")
    )
    monkeypatch.setattr(scraper_instance, "_ensure_event_fields", lambda item: item)
    monkeypatch.setattr(
        scraper_instance, "_resolve_organizer", lambda item: institution
    )
    monkeypatch.setattr(
        scraper_instance, "get_system_user", lambda: institution.created_by
    )

    scraper_instance._save_event_candidate(
        {
            "title_en": "Approved Tracking Event",
            "description_en": "fresh desc",
            "description": "fresh desc",
            "event_type": "conference",
            "domains": "nlp",
            "location": "Algiers",
            "start_date": "2026-10-10",
            "end_date": "2026-10-11",
            "website": "https://approved-tracking.example.com",
            "source_name": "Test Source",
            "organizer": institution,
            "contact_email": "events@example.com",
            "extraction_confidence": 0.75,
        }
    )

    existing.refresh_from_db()
    assert existing.scrape_status == "APPROVED"


@pytest.mark.django_db
def test_event_scrape_rejected_status_can_return_to_pending_review(
    institution,
    monkeypatch,
):
    existing = Event.objects.create(
        title="Rejected Tracking Event",
        title_en="Rejected Tracking Event",
        description="old desc",
        description_en="old desc",
        event_type="conference",
        domains="nlp",
        location="Algiers",
        start_date=date(2026, 10, 10),
        end_date=date(2026, 10, 11),
        website="https://rejected-tracking.example.com",
        organizer=institution,
        contact_email="events@example.com",
        created_by=institution.created_by,
        scrape_status="REJECTED",
        confidence_score=0.2,
    )

    scraper_instance = EventScraper()
    scraper_instance.name = "Test Event Scraper"
    scraper_instance.source = SimpleNamespace(
        name="Test Source",
        category="events",
        scrape_config={},
    )

    monkeypatch.setattr(
        scraper_instance, "passes_min_confidence_to_save", lambda item: True
    )
    monkeypatch.setattr(
        scraper_instance, "_passes_hard_event_rules", lambda item: (True, "")
    )
    monkeypatch.setattr(scraper_instance, "_ensure_event_fields", lambda item: item)
    monkeypatch.setattr(
        scraper_instance, "_resolve_organizer", lambda item: institution
    )
    monkeypatch.setattr(
        scraper_instance, "get_system_user", lambda: institution.created_by
    )

    scraper_instance._save_event_candidate(
        {
            "title_en": "Rejected Tracking Event",
            "description_en": "fresh desc",
            "description": "fresh desc",
            "event_type": "conference",
            "domains": "nlp",
            "location": "Algiers",
            "start_date": "2026-10-10",
            "end_date": "2026-10-11",
            "website": "https://rejected-tracking.example.com",
            "source_name": "Test Source",
            "organizer": institution,
            "contact_email": "events@example.com",
            "extraction_confidence": 0.95,
        }
    )

    existing.refresh_from_db()
    assert existing.scrape_status == "PENDING_REVIEW"


def test_event_hard_rules_allow_last_12_months_window():
    scraper_instance = EventScraper()
    today = timezone.now().date()

    common_payload = {
        "title_en": "Arabic NLP Conference",
        "description_en": "Conference on Arabic NLP and AI shared tasks.",
        "website": "https://example.org/event",
    }

    valid_payload = {
        **common_payload,
        "start_date": today - timedelta(days=300),
    }
    is_valid, reason = scraper_instance._passes_hard_event_rules(valid_payload)
    assert is_valid is True
    assert reason == ""

    too_old_payload = {
        **common_payload,
        "start_date": today - timedelta(days=380),
    }
    is_valid, reason = scraper_instance._passes_hard_event_rules(too_old_payload)
    assert is_valid is False
    assert reason == "event_too_old"


@pytest.mark.django_db
def test_event_scrape_sets_is_past_event_flag(institution, monkeypatch):
    scraper_instance = EventScraper()
    scraper_instance.name = "Test Event Scraper"
    scraper_instance.source = SimpleNamespace(
        name="Test Source",
        category="events",
        scrape_config={},
    )

    monkeypatch.setattr(
        scraper_instance, "passes_min_confidence_to_save", lambda item: True
    )
    monkeypatch.setattr(
        scraper_instance, "_resolve_organizer", lambda item: institution
    )
    monkeypatch.setattr(
        scraper_instance, "get_system_user", lambda: institution.created_by
    )

    past_start = timezone.now().date() - timedelta(days=120)
    scraper_instance._save_event_candidate(
        {
            "title_en": "Archived Arabic NLP Summit",
            "description_en": "Conference on Arabic NLP.",
            "description": "Conference on Arabic NLP.",
            "event_type": "conference",
            "domains": "nlp",
            "location": "Algiers",
            "start_date": past_start.isoformat(),
            "end_date": past_start.isoformat(),
            "website": "https://example.org/archived-event",
            "source_name": "Test Source",
            "contact_email": "events@example.com",
        }
    )

    saved = Event.objects.get(
        title_en="Archived Arabic NLP Summit",
        start_date=past_start,
    )
    assert saved.is_past_event is True


@pytest.mark.django_db
def test_events_negative(scraper, institution):
    is_dup, _ = _check_dup(
        scraper,
        "events",
        {
            "title_en": "Unique event title",
            "website_url": "https://unique-event.example.com",
            "organizer": institution,
            "start_date": date(2027, 1, 1),
            "end_date": date(2027, 1, 2),
        },
    )
    assert is_dup is False


@pytest.mark.django_db
def test_events_rule_specific_negative_cases(scraper, institution):
    Event.objects.create(
        title="Baseline Event",
        title_en="Baseline Event",
        description="desc",
        description_en="desc",
        event_type="conference",
        domains="nlp",
        location="Algiers",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 2),
        website="https://baseline-event.example.com",
        organizer=institution,
        contact_email="events@example.com",
        created_by=institution.created_by,
    )

    # Rule 1 negative: website differs
    dup1, _ = _check_dup(
        scraper,
        "events",
        {
            "title_en": "Completely Different Event",
            "website_url": "https://other.example.com",
            "organizer": institution,
            "start_date": date(2026, 6, 1),
            "end_date": date(2026, 6, 2),
        },
    )
    assert dup1 is False

    # Rule 2 negative: same organizer but no overlap (+3 day window)
    dup2, _ = _check_dup(
        scraper,
        "events",
        {
            "title_en": "Another Different Event",
            "website_url": "https://third.example.com",
            "organizer": institution,
            "start_date": date(2026, 2, 20),
            "end_date": date(2026, 2, 22),
        },
    )
    assert dup2 is False

    # Rule 3 negative: low title similarity
    dup3, _ = _check_dup(
        scraper,
        "events",
        {
            "title_en": "Quantum Physics Expo",
            "website_url": "https://fourth.example.com",
            "organizer": institution,
            "start_date": date(2026, 3, 20),
            "end_date": date(2026, 3, 21),
        },
    )
    assert dup3 is False


@pytest.mark.django_db
def test_tools_dedup_rules(scraper, user):
    NLPTool.objects.create(
        title="AraBERT Toolkit",
        title_en="AraBERT Toolkit",
        title_ar="AraBERT Toolkit",
        description="desc",
        description_en="desc",
        description_ar="desc",
        tool_type="tokenization",
        version="1.0",
        access_link="https://hf.co/tool",
        github_url="https://github.com/example/tool",
        supported_languages="ar",
        language="en",
        author=user,
    )

    dup1, reason1 = _check_dup(
        scraper,
        "tools",
        {"title_en": "x", "github_url": "https://github.com/example/tool"},
    )
    dup2, reason2 = _check_dup(
        scraper,
        "tools",
        {"title_en": "x", "access_link": "https://hf.co/tool"},
    )
    dup3, reason3 = _check_dup(
        scraper,
        "tools",
        {"title_en": "  arabert   toolkit  "},
    )
    dup4, reason4 = _check_dup(
        scraper,
        "tools",
        {"title_en": "AraBERT Toolkits"},
    )
    neg, _ = _check_dup(
        scraper,
        "tools",
        {"title_en": "Completely Different", "access_link": "https://unique.example"},
    )

    assert dup1 and "github_url" in reason1
    assert dup2 and "access_link" in reason2
    assert dup3 and "name exact" in reason3
    assert dup4 and "90%" in reason4
    assert neg is False


@pytest.mark.django_db
def test_tools_rule_specific_negative_cases(scraper, user):
    NLPTool.objects.create(
        title="Arabic Search Tool",
        title_en="Arabic Search Tool",
        title_ar="Arabic Search Tool",
        description="desc",
        description_en="desc",
        description_ar="desc",
        tool_type="tokenization",
        version="1.0",
        access_link="https://tool.example.com",
        github_url="https://github.com/example/search-tool",
        supported_languages="ar",
        language="en",
        author=user,
    )

    n1, _ = _check_dup(
        scraper,
        "tools",
        {"title_en": "x", "github_url": "https://github.com/example/other"},
    )
    n2, _ = _check_dup(
        scraper,
        "tools",
        {"title_en": "x", "access_link": "https://tool.example.net"},
    )
    n3, _ = _check_dup(
        scraper,
        "tools",
        {"title_en": "Arabic Search Engine"},
    )
    n4, _ = _check_dup(
        scraper,
        "tools",
        {"title_en": "Completely Distinct Name"},
    )

    assert n1 is False
    assert n2 is False
    assert n3 is False
    assert n4 is False


@pytest.mark.django_db
def test_news_dedup_rules(scraper, user):
    Post.objects.create(
        author=user,
        title="Arabic NLP Paper",
        title_en="Arabic NLP Paper",
        content="c",
        content_en="c",
        slug="arabic-nlp-paper",
        arxiv_id="2401.00001",
        doi="10.1000/test-doi",
        source_url="https://arxiv.org/abs/2401.00001",
    )

    dup1, reason1 = _check_dup(
        scraper,
        "news",
        {"title_en": "x", "arxiv_id": "2401.00001"},
    )
    dup2, reason2 = _check_dup(
        scraper,
        "news",
        {"title_en": "x", "doi": "10.1000/test-doi"},
    )
    dup3, reason3 = _check_dup(
        scraper,
        "news",
        {"title_en": "x", "source_url": "https://arxiv.org/abs/2401.00001/"},
    )
    dup4, reason4 = _check_dup(
        scraper,
        "news",
        {"title_en": "Arabic NLP Paper!"},
    )
    neg, _ = _check_dup(
        scraper,
        "news",
        {"title_en": "Novel paper", "arxiv_id": "2501.12345", "doi": "10.1111/unique"},
    )

    assert dup1 and "arxiv_id" in reason1
    assert dup2 and "doi" in reason2
    assert dup3 and "source_url" in reason3
    assert dup4 and "85%" in reason4
    assert neg is False


@pytest.mark.django_db
def test_news_rule_specific_negative_cases(scraper, user):
    Post.objects.create(
        author=user,
        title="Baseline News",
        title_en="Baseline News",
        content="c",
        content_en="c",
        slug="baseline-news",
        arxiv_id="2601.00001",
        doi="10.1000/base-news",
        source_url="https://news.example.com/paper",
    )

    n1, _ = _check_dup(scraper, "news", {"title_en": "x", "arxiv_id": "2601.99999"})
    n2, _ = _check_dup(scraper, "news", {"title_en": "x", "doi": "10.1000/other"})
    n3, _ = _check_dup(
        scraper,
        "news",
        {"title_en": "x", "source_url": "https://news.example.com/other"},
    )
    n4, _ = _check_dup(scraper, "news", {"title_en": "Different Headline Entirely"})

    assert n1 is False
    assert n2 is False
    assert n3 is False
    assert n4 is False


@pytest.mark.django_db
def test_courses_dedup_rules(scraper, user, institution):
    Course.objects.create(
        title="Intro to NLP",
        title_en="Intro to NLP",
        title_ar="Intro to NLP",
        description="Instructor: John Doe",
        description_en="Instructor: John Doe",
        description_ar="Instructor: John Doe",
        field="nlp",
        academic_level="master",
        teacher=user,
        institution=institution,
        academic_year="2026-2027",
        access_link="https://courses.example.com/nlp",
        language="en",
        author=user,
    )

    dup1, reason1 = _check_dup(
        scraper,
        "courses",
        {"title_en": "x", "access_link": "https://courses.example.com/nlp"},
    )
    dup2, reason2 = _check_dup(
        scraper,
        "courses",
        {"title_en": "Intro to NLP", "instructor": "John Doe"},
    )
    dup3, reason3 = _check_dup(
        scraper,
        "courses",
        {"title_en": "Intro to NLP!"},
    )
    neg, _ = _check_dup(
        scraper,
        "courses",
        {
            "title_en": "New Course",
            "instructor": "Jane Roe",
            "access_link": "https://courses.example.com/new",
        },
    )

    assert dup1 and "access_link" in reason1
    assert dup2 and "title + instructor" in reason2
    assert dup3 and "90%" in reason3
    assert neg is False


@pytest.mark.django_db
def test_courses_rule_specific_negative_cases(scraper, user, institution):
    Course.objects.create(
        title="Arabic NLP Fundamentals",
        title_en="Arabic NLP Fundamentals",
        title_ar="Arabic NLP Fundamentals",
        description="Instructor: Jane Doe",
        description_en="Instructor: Jane Doe",
        description_ar="Instructor: Jane Doe",
        field="nlp",
        academic_level="master",
        teacher=user,
        institution=institution,
        academic_year="2027-2028",
        access_link="https://courses.example.com/arabic-nlp",
        language="en",
        author=user,
    )

    n1, _ = _check_dup(
        scraper,
        "courses",
        {"title_en": "x", "access_link": "https://courses.example.com/unique"},
    )
    n2, _ = _check_dup(
        scraper,
        "courses",
        {"title_en": "Arabic NLP Fundamentals", "instructor": "John Smith"},
    )
    n3, _ = _check_dup(scraper, "courses", {"title_en": "Statistical Physics Intro"})

    assert n1 is False
    assert n2 is True
    assert n3 is False


@pytest.mark.django_db
def test_institutions_dedup_rules(scraper, country, user):
    Institution.objects.create(
        name="University of Testing",
        name_en="University of Testing",
        name_ar="جامعة الاختبار",
        acronym="UOT",
        ror_id="https://ror.org/12345",
        type="University",
        country=country,
        city="Algiers",
        city_en="Algiers",
        city_ar="الجزائر",
        website="https://www.univ-test.dz/",
        email="contact@univ-test.dz",
        address="Algiers",
        address_en="Algiers",
        address_ar="الجزائر",
        description="desc",
        description_en="desc",
        description_ar="desc",
        created_by=user,
        approval_status="approved",
    )

    dup1, reason1 = _check_dup(
        scraper,
        "institutions",
        {"name_en": "X", "ror_id": "https://ror.org/12345"},
    )
    dup2, reason2 = _check_dup(
        scraper,
        "institutions",
        {"name_en": "X", "website_url": "https://univ-test.dz"},
    )
    dup3, reason3 = _check_dup(
        scraper,
        "institutions",
        {"name_en": "University of Testin"},
    )
    neg, _ = _check_dup(
        scraper,
        "institutions",
        {"name_en": "Independent Lab", "website_url": "https://independent.example"},
    )

    assert dup1 and "ror_id" in reason1
    assert dup2 and "website_url" in reason2
    assert dup3 and "90%" in reason3
    assert neg is False


@pytest.mark.django_db
def test_institutions_rule_specific_negative_cases(scraper, country, user):
    Institution.objects.create(
        name="Baseline Institute",
        name_en="Baseline Institute",
        name_ar="معهد أساسي",
        acronym="BI",
        ror_id="https://ror.org/baseline",
        type="University",
        country=country,
        city="Algiers",
        city_en="Algiers",
        city_ar="الجزائر",
        website="https://www.baseline.dz/",
        email="contact@baseline.dz",
        address="Algiers",
        address_en="Algiers",
        address_ar="الجزائر",
        description="desc",
        description_en="desc",
        description_ar="desc",
        created_by=user,
        approval_status="approved",
    )

    n1, _ = _check_dup(
        scraper, "institutions", {"name_en": "X", "ror_id": "https://ror.org/other"}
    )
    n2, _ = _check_dup(
        scraper, "institutions", {"name_en": "X", "website_url": "https://different.dz"}
    )
    n3, _ = _check_dup(scraper, "institutions", {"name_en": "Another Unique Lab"})

    assert n1 is False
    assert n2 is False
    assert n3 is False


@pytest.mark.django_db
def test_short_circuit_returns_first_match(scraper, institution):
    Event.objects.create(
        title="Deep Arabic NLP Summit",
        title_en="Deep Arabic NLP Summit",
        description="desc",
        description_en="desc",
        event_type="conference",
        domains="nlp",
        location="Algiers",
        start_date=date(2026, 11, 10),
        end_date=date(2026, 11, 11),
        website="https://priority.example.com",
        organizer=institution,
        contact_email="events@example.com",
        created_by=institution.created_by,
    )

    is_dup, reason = _check_dup(
        scraper,
        "events",
        {
            "title_en": "Deep Arabic NLP Summit!",
            "website_url": "https://priority.example.com",
            "organizer": institution,
            "start_date": date(2026, 11, 10),
            "end_date": date(2026, 11, 11),
        },
    )

    assert is_dup is True
    assert reason == "event website_url exact match"


@pytest.mark.django_db
def test_semantic_fallback_called_only_after_deterministic_fail(scraper, monkeypatch):
    calls = {"count": 0}

    def _fake_find_semantic_duplicate(title, category, threshold=0.88):
        calls["count"] += 1
        return None

    monkeypatch.setattr(
        "scraping.embeddings.find_semantic_duplicate", _fake_find_semantic_duplicate
    )

    # Deterministic duplicate (no semantic call expected)
    dup_tool = NLPTool.objects.create(
        title="Deterministic Tool",
        title_en="Deterministic Tool",
        title_ar="Deterministic Tool",
        description="desc",
        description_en="desc",
        description_ar="desc",
        tool_type="tokenization",
        version="1.0",
        access_link="https://dedup.example/tool",
        supported_languages="ar",
        language="en",
        author=get_user_model().objects.create_user(  # type: ignore[call-arg]
            email="semantic@test.com",
            password="x",
            full_name_en="Semantic User",
            full_name_ar="مستخدم",
        ),
    )
    assert dup_tool is not None

    dup, _ = _check_dup(
        scraper,
        "tools",
        {"title_en": "Something else", "access_link": "https://dedup.example/tool"},
    )
    assert dup is True
    assert calls["count"] == 0

    # Deterministic miss (semantic call expected)
    dup2, _ = _check_dup(
        scraper,
        "tools",
        {"title_en": "Unique title", "access_link": "https://unique.example/tool"},
    )
    assert dup2 is False
    assert calls["count"] == 1
