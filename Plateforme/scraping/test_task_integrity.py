from unittest.mock import MagicMock

import pytest

from scraping.models import ScrapingRun, ScrapingSourceHealth
from scraping.tasks import run_scraper_task


@pytest.mark.django_db
def test_task_marks_run_failed_on_scraper_exception():
    run = ScrapingRun.objects.create(category="news", status="pending")

    with pytest.raises(RuntimeError), pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "scraping.tasks.get_scraper",
            lambda *_: (_ for _ in ()).throw(RuntimeError("scraper boom")),
        )
        run_scraper_task.apply(
            kwargs={"category": "news", "run_id": str(run.id)},
            task_id="task-fail-1",
        ).get(propagate=True)

    run.refresh_from_db()
    assert run.status == "failed"
    assert "scraper boom" in run.errors


@pytest.mark.django_db
def test_task_updates_run_completed_on_success():
    run = ScrapingRun.objects.create(category="news", status="pending")
    fake_scraper = MagicMock()
    fake_scraper.run.return_value = {
        "items_found": 3,
        "items_created": 2,
        "items_skipped": 1,
        "errors": [],
        "results": [],
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("scraping.tasks.get_scraper", lambda *_: fake_scraper)
        result = run_scraper_task.apply(
            kwargs={"category": "news", "run_id": str(run.id)},
            task_id="task-success-1",
        ).get(propagate=True)

    run.refresh_from_db()
    assert result["status"] == "success"
    assert run.status == "completed"
    assert run.completed_at is not None


@pytest.mark.django_db
def test_task_does_not_run_if_circuit_open():
    run = ScrapingRun.objects.create(category="news", status="pending")
    ScrapingSourceHealth.objects.create(
        category="news",
        source_name="all_sources",
        circuit_state="open",
    )

    fake_scraper = MagicMock()
    fake_scraper.run.return_value = {
        "items_found": 0,
        "items_created": 0,
        "items_skipped": 0,
        "errors": [],
        "results": [],
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("scraping.tasks.get_scraper", lambda *_: fake_scraper)
        run_scraper_task.apply(
            kwargs={"category": "news", "run_id": str(run.id)},
            task_id="task-circuit-1",
        ).get(propagate=True)

    fake_scraper.scrape.assert_not_called()


@pytest.mark.django_db
def test_task_respects_max_retries_config():
    run = ScrapingRun.objects.create(category="news", status="pending")
    fake_scraper = MagicMock()
    fake_scraper.run.side_effect = RuntimeError("always failing")

    with pytest.raises(RuntimeError), pytest.MonkeyPatch.context() as mp:
        mp.setattr("scraping.tasks.get_scraper", lambda *_: fake_scraper)
        run_scraper_task.apply(
            kwargs={"category": "news", "run_id": str(run.id)},
            task_id="task-retry-1",
        ).get(propagate=True)

    run.refresh_from_db()
    assert run.status == "failed"
    assert fake_scraper.run.call_count == 1
