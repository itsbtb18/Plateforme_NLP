from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from django.db import close_old_connections
from django.utils import timezone

from scraping.models import ScrapingSourceHealth


pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def _record_failure_worker(pk):
    close_old_connections()
    try:
        row = ScrapingSourceHealth.objects.get(pk=pk)
        row.record_failure("simulated")
    finally:
        close_old_connections()


def _is_available_worker(pk):
    close_old_connections()
    try:
        row = ScrapingSourceHealth.objects.get(pk=pk)
        return row.is_available()
    finally:
        close_old_connections()


def test_source_health_created_and_updated():
    health = ScrapingSourceHealth.objects.create(
        category="news",
        source_name="circuit-source-1",
        base_url="https://example.org",
    )
    health.record_success(response_time=0.2)

    health.refresh_from_db()
    assert health.total_attempts == 1
    assert health.total_successes == 1
    assert health.last_attempt_at is not None


def test_circuit_breaker_transitions_are_recorded():
    health = ScrapingSourceHealth.objects.create(
        category="news",
        source_name="circuit-source-2",
        base_url="https://example.org",
    )

    for _ in range(3):
        health.record_failure("max_failures")

    health.refresh_from_db()
    assert health.circuit_state == "open"
    assert health.last_error == "max_failures"


def test_concurrent_state_updates_do_not_corrupt_row():
    health = ScrapingSourceHealth.objects.create(
        category="news",
        source_name="circuit-source-3",
        base_url="https://example.org",
    )

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_record_failure_worker, health.pk) for _ in range(4)]
        for future in futures:
            future.result()

    health.refresh_from_db()
    assert health.total_attempts == 4
    assert health.total_failures == 4
    assert health.consecutive_failures >= 1


def test_recovery_from_down_to_healthy():
    health = ScrapingSourceHealth.objects.create(
        category="news",
        source_name="circuit-source-4",
        base_url="https://example.org",
        circuit_state="open",
        circuit_opened_at=timezone.now() - timedelta(seconds=60),
        circuit_cooldown_seconds=0,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_is_available_worker, health.pk) for _ in range(2)]
        results = [f.result() for f in futures]

    health.refresh_from_db()
    assert sum(bool(r) for r in results) == 1
    assert health.circuit_state == "half_open"
