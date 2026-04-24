from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from scraping.models import ScrapingSourceHealth


class ScrapingSourceHealthConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        if connection.vendor == "sqlite":
            self.skipTest("SQLite does not provide reliable multi-thread write concurrency")

        self.health = ScrapingSourceHealth.objects.create(
            category="news",
            source_name="Concurrency Test Source",
            base_url="https://example.com",
        )

    def _worker_record_failure(self, pk):
        close_old_connections()
        try:
            row = ScrapingSourceHealth.objects.get(pk=pk)
            row.record_failure("simulated failure")
        finally:
            close_old_connections()

    def _worker_is_available(self, pk):
        close_old_connections()
        try:
            row = ScrapingSourceHealth.objects.get(pk=pk)
            return row.is_available()
        finally:
            close_old_connections()

    def test_parallel_failures_do_not_lose_counter_updates(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self._worker_record_failure, self.health.pk)
                for _ in range(2)
            ]
            for future in futures:
                future.result()

        self.health.refresh_from_db()
        self.assertEqual(self.health.total_attempts, 2)
        self.assertEqual(self.health.total_failures, 2)
        self.assertEqual(self.health.consecutive_failures, 2)

    def test_half_open_probe_claim_is_atomic(self):
        self.health.circuit_state = "open"
        self.health.circuit_opened_at = timezone.now() - timedelta(seconds=60)
        self.health.circuit_cooldown_seconds = 0
        self.health.last_attempt_at = None
        self.health.save(
            update_fields=[
                "circuit_state",
                "circuit_opened_at",
                "circuit_cooldown_seconds",
                "last_attempt_at",
            ]
        )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self._worker_is_available, self.health.pk)
                for _ in range(2)
            ]
            results = [f.result() for f in futures]

        self.health.refresh_from_db()
        self.assertEqual(sum(bool(r) for r in results), 1)
        self.assertEqual(self.health.circuit_state, "half_open")
        self.assertIsNotNone(self.health.last_attempt_at)
