from types import SimpleNamespace

from bs4 import BeautifulSoup

from scraping.scrapers.base import BaseScraper
from scraping.scrapers.courses import CourseScraper
from scraping.scrapers.events import EventScraper


def _source(url="https://example.org", tier=None, name="source"):
    scrape_config = {}
    if tier is not None:
        scrape_config["tier"] = tier
    return SimpleNamespace(name=name, url=url, base_url="", scrape_config=scrape_config)


def test_courses_scrape_runs_all_tiers_when_no_tier_config(monkeypatch):
    scraper = CourseScraper.__new__(CourseScraper)

    calls = []
    monkeypatch.setattr(scraper, "get_active_sources", lambda: [_source(tier=None)])
    monkeypatch.setattr(scraper, "get_default_sources", lambda: [])
    monkeypatch.setattr(
        scraper,
        "_scrape_tier_1_algerian_courses",
        lambda: calls.append("tier1"),
    )
    monkeypatch.setattr(
        scraper,
        "_scrape_tier_2_arabic_courses",
        lambda: calls.append("tier2"),
    )
    monkeypatch.setattr(
        scraper,
        "_scrape_tier_3_global_courses",
        lambda: calls.append("tier3"),
    )

    scraper.scrape()

    assert calls == ["tier1", "tier2", "tier3"]


def test_courses_scrape_uses_default_sources_and_selected_tier(monkeypatch):
    scraper = CourseScraper.__new__(CourseScraper)

    calls = []
    monkeypatch.setattr(scraper, "get_active_sources", lambda: [])
    monkeypatch.setattr(
        scraper,
        "get_default_sources",
        lambda: [_source(tier=2, name="default-tier2")],
    )
    monkeypatch.setattr(
        scraper,
        "_scrape_tier_1_algerian_courses",
        lambda: calls.append("tier1"),
    )
    monkeypatch.setattr(
        scraper,
        "_scrape_tier_2_arabic_courses",
        lambda: calls.append("tier2"),
    )
    monkeypatch.setattr(
        scraper,
        "_scrape_tier_3_global_courses",
        lambda: calls.append("tier3"),
    )

    scraper.scrape()

    assert calls == ["tier2"]


def test_courses_tier_method_marks_checkpoint_sources_done(monkeypatch):
    scraper = CourseScraper.__new__(CourseScraper)

    marked = []

    class _Checkpoint:
        @staticmethod
        def is_source_done(_source_name):
            return False

        @staticmethod
        def mark_source_done(source_name):
            marked.append(source_name)

    scraper._checkpoint = _Checkpoint()

    monkeypatch.setattr(scraper, "_scrape_rss_course_sources", lambda _sources: None)
    monkeypatch.setattr(scraper, "_scrape_algerian_university_ocw", lambda: None)
    monkeypatch.setattr(scraper, "_scrape_cerist_training_programs", lambda: None)
    monkeypatch.setattr(
        scraper,
        "_scrape_youtube_playlists",
        lambda _terms, source_name: None,
    )
    monkeypatch.setattr(scraper, "_scrape_fun_mooc_fr", lambda: None)

    scraper._scrape_tier_1_algerian_courses()

    assert marked == [
        "tier1_rss",
        "algerian_university_ocw",
        "cerist_training",
        "youtube_algeria_arabic",
        "fun_mooc_fr",
    ]


def test_events_scrape_falls_back_to_default_sources(monkeypatch):
    scraper = EventScraper.__new__(EventScraper)
    scraper.items_created = 0

    collected_calls = []
    saved = []

    monkeypatch.setattr(scraper, "get_active_sources", lambda: [])
    monkeypatch.setattr(
        scraper,
        "get_default_sources",
        lambda: [_source(url="https://events.example.org", tier=2, name="default")],
    )
    monkeypatch.setattr(
        scraper,
        "_collect_from_source",
        lambda **kwargs: collected_calls.append(kwargs) or [{"title": "candidate"}],
    )
    monkeypatch.setattr(
        scraper, "_deduplicate_combined_candidates", lambda items: items
    )
    monkeypatch.setattr(
        scraper, "_save_event_candidate", lambda item: saved.append(item)
    )

    scraper.scrape()

    assert collected_calls
    assert collected_calls[0]["base_url"] == "https://events.example.org"
    assert len(saved) == 1


def test_events_scrape_uses_default_when_active_urls_are_empty(monkeypatch):
    scraper = EventScraper.__new__(EventScraper)
    scraper.items_created = 0

    collected_calls = []

    monkeypatch.setattr(
        scraper,
        "get_active_sources",
        lambda: [_source(url="", tier=1, name="empty-active")],
    )
    monkeypatch.setattr(
        scraper,
        "get_default_sources",
        lambda: [
            _source(
                url="https://events-default.example.org",
                tier=3,
                name="default-with-url",
            )
        ],
    )
    monkeypatch.setattr(
        scraper,
        "_collect_from_source",
        lambda **kwargs: collected_calls.append(kwargs) or [],
    )
    monkeypatch.setattr(
        scraper, "_deduplicate_combined_candidates", lambda items: items
    )

    scraper.scrape()

    assert collected_calls
    assert collected_calls[0]["base_url"] == "https://events-default.example.org"


def test_events_collect_html_paths_respects_source_max_pages(monkeypatch):
    scraper = EventScraper.__new__(EventScraper)
    BaseScraper.__init__(scraper)
    visited_urls = []

    def fake_fetch_listing_page(url, timeout=None):
        visited_urls.append(url)
        return BeautifulSoup(
            """
            <html><body>
              <article>
                <h2>NLP Event Page</h2>
                <p>Conference on natural language processing in 2026</p>
                <a href="/event/details">Details</a>
              </article>
            </body></html>
            """,
            "html.parser",
        )

    monkeypatch.setattr(scraper, "fetch_listing_page", fake_fetch_listing_page)

    scraper._collect_html_paths(
        base_url="https://events.example.org",
        paths=["/agenda"],
        source_name="Test Events Source",
        priority=25,
        tier=1,
        default_location="Algiers",
        timeout=5,
        scrape_config={"max_pages": 2},
    )

    assert len(visited_urls) == 2
    assert visited_urls[0] == "https://events.example.org/agenda"
    assert visited_urls[1] == "https://events.example.org/agenda?page=2"


def test_events_extract_candidates_uses_admin_selectors(monkeypatch):
    scraper = EventScraper.__new__(EventScraper)
    BaseScraper.__init__(scraper)

    html = """
    <html><body>
      <article class='event-item'>
        <span class='admin-title'>Admin Event Title</span>
        <div class='admin-body'>Conference in Algiers about NLP.</div>
        <time datetime='2026-05-12'>2026-05-12</time>
        <a class='admin-link' href='/events/42'>Details</a>
      </article>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    source = _source(url="https://events.example.org", name="events-source")
    source.css_selectors = {
        "title_selector": ".admin-title",
        "desc_selector": ".admin-body",
        "date_selector": "time",
        "link_selector": "a.admin-link",
    }

    candidates = scraper._extract_event_candidates_from_html(
        soup=soup,
        page_url="https://events.example.org/list",
        source_name="events-source",
        source=source,
        default_location="Unknown",
        priority=25,
        tier=1,
    )

    assert candidates
    assert candidates[0]["title"] == "Admin Event Title"
    assert candidates[0]["website"] == "https://events.example.org/events/42"


def test_courses_generic_site_uses_admin_selectors_when_configured(monkeypatch):
    scraper = CourseScraper.__new__(CourseScraper)
    BaseScraper.__init__(scraper)

    source = _source(url="https://courses.example.org", name="courses-source")
    source.css_selectors = {
        "title_selector": ".admin-title",
        "desc_selector": ".admin-body",
        "link_selector": "a.admin-link",
    }

    monkeypatch.setattr(scraper, "_ensure_institution", lambda **_kwargs: object())
    monkeypatch.setattr(
        scraper,
        "fetch_listing_page",
        lambda *_args, **_kwargs: BeautifulSoup(
            """
            <html><body>
              <article>
                <h2>Heuristic Course</h2>
                <span class='admin-title'>Admin Course</span>
                <div class='admin-body'>Admin body for NLP course</div>
                <a class='admin-link' href='/course/admin'>Open</a>
              </article>
            </body></html>
            """,
            "html.parser",
        ),
    )
    monkeypatch.setattr(
        scraper,
        "_extract_catalog_cards",
        lambda *_args, **_kwargs: [
            {
                "title": "Heuristic Course",
                "description": "Heuristic Description",
                "url": "https://courses.example.org/course/heuristic",
                "raw_html": """
                    <article>
                      <h2>Heuristic Course</h2>
                      <span class='admin-title'>Admin Course</span>
                      <div class='admin-body'>Admin body for NLP course</div>
                      <a class='admin-link' href='/course/admin'>Open</a>
                    </article>
                """,
            }
        ],
    )
    monkeypatch.setattr(scraper, "_is_ai_nlp_related", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        scraper,
        "_build_course_metadata",
        lambda **_kwargs: {
            "field": "nlp",
            "level": "bachelor",
            "instructor": "",
            "duration": "",
            "enrollment_url": "",
            "thumbnail_url": "",
            "is_free": True,
            "price": None,
            "certificate_available": False,
            "start_date": None,
        },
    )

    created = []
    monkeypatch.setattr(
        scraper, "_create_course", lambda **kwargs: created.append(kwargs)
    )

    scraper._scrape_generic_mooc_site(
        base_url="https://courses.example.org",
        source_name="courses-source",
        country_name="Algeria",
        country_code="DZ",
        source=source,
    )

    assert created
    assert created[0]["title"] == "Admin Course"
    assert created[0]["website"] == "https://courses.example.org/course/admin"


def test_courses_generic_site_falls_back_silently_when_selectors_empty(monkeypatch):
    scraper = CourseScraper.__new__(CourseScraper)
    BaseScraper.__init__(scraper)

    source = _source(url="https://courses.example.org", name="courses-source")
    source.css_selectors = {}

    monkeypatch.setattr(scraper, "_ensure_institution", lambda **_kwargs: object())
    monkeypatch.setattr(
        scraper,
        "fetch_listing_page",
        lambda *_args, **_kwargs: BeautifulSoup(
            "<html><body><article><a href='/course/1'>Heuristic Course</a><p>NLP content</p></article></body></html>",
            "html.parser",
        ),
    )
    monkeypatch.setattr(
        scraper,
        "_extract_catalog_cards",
        lambda *_args, **_kwargs: [
            {
                "title": "Heuristic Course",
                "description": "NLP content from fallback",
                "url": "https://courses.example.org/course/1",
                "raw_html": "<article><a href='/course/1'>Heuristic Course</a><p>NLP content</p></article>",
            }
        ],
    )
    monkeypatch.setattr(scraper, "_is_ai_nlp_related", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        scraper,
        "_build_course_metadata",
        lambda **_kwargs: {
            "field": "nlp",
            "level": "bachelor",
            "instructor": "",
            "duration": "",
            "enrollment_url": "",
            "thumbnail_url": "",
            "is_free": True,
            "price": None,
            "certificate_available": False,
            "start_date": None,
        },
    )

    warnings = []
    monkeypatch.setattr(
        "scraping.scrapers.courses.logger.warning",
        lambda *args, **kwargs: warnings.append((args, kwargs)),
    )

    created = []
    monkeypatch.setattr(
        scraper, "_create_course", lambda **kwargs: created.append(kwargs)
    )

    scraper._scrape_generic_mooc_site(
        base_url="https://courses.example.org",
        source_name="courses-source",
        country_name="Algeria",
        country_code="DZ",
        source=source,
    )

    assert created
    assert created[0]["title"] == "Heuristic Course"
    assert not warnings
