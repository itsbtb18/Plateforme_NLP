import uuid
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_scraper():
    with patch("scraping.tasks.get_scraper") as mock_get:
        scraper_inst = MagicMock()
        scraper_inst.run.return_value = {
            "items_found": 0,
            "items_created": 0,
            "items_skipped": 0,
            "errors": [],
            "results": []
        }
        mock_get.return_value = scraper_inst
        yield scraper_inst

@pytest.mark.django_db
def test_invalid_run_id_no_recreate():
    """Test 1: Invalid run_id and allow_run_recreate=False raises ValueError."""
    from scraping.tasks import run_scraper_task

    run_id = str(uuid.uuid4())

    with patch("scraping.tasks.logger") as mock_logger:
        with pytest.raises(ValueError) as exc:
            run_scraper_task.apply(
                kwargs={
                    "category": "events",
                    "run_id": run_id,
                    "allow_run_recreate": False,
                },
                task_id="test-task-123",
            ).get(propagate=True)

        assert run_id in str(exc.value)
        mock_logger.error.assert_called_with(
            "run_id_not_found",
            extra={
                "run_id": run_id,
                "category": "events",
                "task_id": "test-task-123",
            },
        )


@pytest.mark.django_db
def test_invalid_run_id_recreate(mock_scraper):
    """Test 2: Invalid run_id and allow_run_recreate=True creates new ScrapingRun."""
    from scraping.models import ScrapingRun
    from scraping.tasks import run_scraper_task

    run_id = str(uuid.uuid4())

    with patch("scraping.tasks.logger") as mock_logger:
        result = run_scraper_task.apply(
            kwargs={
                "category": "events",
                "run_id": run_id,
                "allow_run_recreate": True,
            },
            task_id="test-task-123",
        ).get(propagate=True)

    assert result["status"] == "success"

    # Verify warning was logged
    mock_logger.warning.assert_called_with(
        "run_recreated",
        extra={"run_id": run_id, "category": "events"},
    )

    # Verify a ScrapingRun was created (but it takes a new ID)
    assert ScrapingRun.objects.filter(category="events").exists()


@pytest.mark.django_db
def test_valid_run_id(mock_scraper):
    """Test 3: Valid run_id uses existing run, does not create a new one."""
    from scraping.models import ScrapingRun
    from scraping.tasks import run_scraper_task

    run = ScrapingRun.objects.create(category="events", status="pending")
    initial_count = ScrapingRun.objects.count()

    result = run_scraper_task.apply(
        kwargs={
            "category": "events",
            "run_id": str(run.id),
            "allow_run_recreate": False,
        },
        task_id="test-task-123",
    ).get(propagate=True)

    assert result["status"] == "success"
    assert result["run_id"] == str(run.id)

    # Verify we used existing run, total runs should still be the initial count
    assert ScrapingRun.objects.count() == initial_count
    run.refresh_from_db()
    assert run.status == "completed"
