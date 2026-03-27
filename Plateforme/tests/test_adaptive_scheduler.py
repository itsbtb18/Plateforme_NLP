from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from scraping.adaptive_scheduler import AdaptiveScheduler
from scraping.models import ScrapingRun, ScrapingSource


@pytest.mark.django_db
def test_compute_optimal_interval_defaults_to_medium_with_insufficient_runs():
    source = ScrapingSource.objects.create(
        name="Sparse Source",
        category="news",
        is_active=True,
    )

    now = timezone.now()
    for i in range(2):
        run = ScrapingRun.objects.create(
            category="news",
            source=source,
            status="completed",
            items_created=1,
        )
        ScrapingRun.objects.filter(pk=run.pk).update(started_at=now - timedelta(days=i))

    tier, interval = AdaptiveScheduler(lookback_runs=30).compute_optimal_interval(
        source.id
    )

    assert tier == "medium"
    assert interval == AdaptiveScheduler.TIERS["medium"]


@pytest.mark.django_db
def test_compute_optimal_interval_classifies_very_high_when_rate_exceeds_one_per_day():
    source = ScrapingSource.objects.create(
        name="Fast News",
        category="news",
        is_active=True,
    )

    now = timezone.now()
    counts = [6, 5, 4, 5]
    for index, count in enumerate(counts):
        run = ScrapingRun.objects.create(
            category="news",
            source=source,
            status="completed",
            items_created=count,
        )
        ScrapingRun.objects.filter(pk=run.pk).update(
            started_at=now - timedelta(days=index)
        )

    tier, interval = AdaptiveScheduler(lookback_runs=10).compute_optimal_interval(
        source.id
    )

    assert tier == "very_high"
    assert interval == AdaptiveScheduler.TIERS["very_high"]


@pytest.mark.django_db
def test_update_source_schedule_updates_periodic_task_and_source_fields():
    from django_celery_beat.models import PeriodicTask

    source = ScrapingSource.objects.create(
        name="ACL Anthology",
        category="news",
        is_active=True,
    )

    now = timezone.now()
    for index in range(3):
        run = ScrapingRun.objects.create(
            category="news",
            source=source,
            status="completed",
            items_created=3,
        )
        ScrapingRun.objects.filter(pk=run.pk).update(
            started_at=now - timedelta(days=index + 1)
        )

    scheduler = AdaptiveScheduler(lookback_runs=30)
    result = scheduler.update_source_schedule(source.id)

    source.refresh_from_db()
    task = PeriodicTask.objects.get(name="scraping_acl-anthology")

    assert result["source"] == "ACL Anthology"
    assert result["new_tier"] == source.schedule_tier
    assert source.schedule_interval_hours == task.interval.every
    assert task.task == "scraping.tasks.run_scraper_task"
    assert '"source_id"' in (task.kwargs or "")


@pytest.mark.django_db
def test_update_all_sources_disables_legacy_fixed_tasks_and_updates_active_sources():
    from django_celery_beat.models import IntervalSchedule, PeriodicTask

    active = ScrapingSource.objects.create(
        name="Active Source",
        category="events",
        is_active=True,
    )
    ScrapingSource.objects.create(
        name="Inactive Source",
        category="events",
        is_active=False,
    )

    now = timezone.now()
    for index in range(3):
        run = ScrapingRun.objects.create(
            category="events",
            source=active,
            status="completed",
            items_created=2,
        )
        ScrapingRun.objects.filter(pk=run.pk).update(
            started_at=now - timedelta(days=index + 1)
        )

    interval = IntervalSchedule.objects.create(every=24, period=IntervalSchedule.HOURS)
    PeriodicTask.objects.create(
        name="Auto-scrape News Daily",
        task="scraping.tasks.run_scraper_task",
        interval=interval,
        enabled=True,
    )

    results = AdaptiveScheduler(lookback_runs=10).update_all_sources()

    assert len(results) == 1
    assert results[0]["source"] == "Active Source"
    assert PeriodicTask.objects.get(name="Auto-scrape News Daily").enabled is False
