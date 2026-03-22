from unittest.mock import patch
from typing import Any, cast

import pytest

from scraping.models import ScrapingRun
from scraping.tasks import run_scraper_task


pytestmark = [pytest.mark.django_db, pytest.mark.integration]


@pytest.mark.parametrize(
    "category,model_path,payload",
    [
        (
            "events",
            "events.models.Event",
            {
                "title": "Pipeline Event",
                "title_en": "Pipeline Event",
                "title_ar": "حدث خط الأنابيب",
                "description": "desc",
                "description_en": "desc",
                "description_ar": "وصف",
                "event_type": "conference",
                "domains": "nlp",
                "location": "Algiers",
                "start_date": "2026-10-01",
                "end_date": "2026-10-02",
                "website": "https://pipeline-event.example.org",
                "contact_email": "pipeline@example.org",
                "approval_status": "approved",
            },
        ),
        (
            "tools",
            "resources.models.NLPTool",
            {
                "title": "Pipeline Tool",
                "title_en": "Pipeline Tool",
                "title_ar": "أداة",
                "description": "desc",
                "description_en": "desc",
                "description_ar": "وصف",
                "tool_type": "tokenization",
                "version": "1.0",
                "access_link": "https://pipeline-tool.example.org",
                "supported_languages": "ar,en",
                "language": "en",
                "approval_status": "approved",
            },
        ),
    ],
)
def test_run_task_persists_items_and_dedups_second_pass(
    category,
    model_path,
    payload,
    django_user_model,
):
    run = ScrapingRun.objects.create(category=category, status="pending")
    user = django_user_model.objects.create_user(
        email="pipeline-owner@example.org",
        password="testpass123",
        full_name_en="Pipeline Owner",
        full_name_ar="مالك",
    )

    if category == "events":
        payload["created_by"] = user
    if category == "tools":
        payload["author"] = user

    class StubScraper:
        calls = 0

        def run(self):
            type(self).calls += 1
            if type(self).calls == 1:
                return {
                    "items_found": 1,
                    "items_created": 1,
                    "items_skipped": 0,
                    "errors": [],
                    "results": [payload],
                }
            return {
                "items_found": 1,
                "items_created": 0,
                "items_skipped": 1,
                "errors": [],
                "results": [payload],
            }

    with patch("scraping.tasks.get_scraper", return_value=StubScraper()):
        task = cast(Any, run_scraper_task)
        result_1 = task.run(category, str(run.id))
        result_2 = task.run(category, str(run.id))

    assert result_1["items_created"] == 1
    assert result_2["items_skipped"] == 1


def test_pipeline_calls_media_and_enrichment_hooks(monkeypatch):
    from scraping.scrapers.events import EventScraper

    scraper = EventScraper()

    media_called = {"count": 0}
    enrich_called = {"count": 0}

    def _fake_download_media(data, category):
        media_called["count"] += 1
        return data

    def _fake_enrich(data, category):
        enrich_called["count"] += 1
        data["title_en"] = data.get("title_en") or data.get("title")
        data["description_en"] = data.get("description_en") or data.get("description")
        data["description_ar"] = data.get("description_ar") or data.get("description")
        data["title_ar"] = data.get("title_ar") or data.get("title")
        return data

    monkeypatch.setattr(scraper, "_download_media", _fake_download_media)
    monkeypatch.setattr("scraping.scrapers.events.enrich_scraped_item", _fake_enrich)
    monkeypatch.setattr(scraper, "_resolve_organizer", lambda candidate: None)

    candidate = {
        "title": "Event pipeline",
        "description": "Pipeline content",
        "start_date": "2026-08-10",
        "website": "https://event-pipeline.example.org",
    }

    scraper._save_event_candidate(candidate)

    assert media_called["count"] >= 1
    assert enrich_called["count"] >= 1
