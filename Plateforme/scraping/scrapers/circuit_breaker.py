import logging
import time

from django.core.cache import cache

logger = logging.getLogger(__name__)


class RedisCircuitBreaker:
    """Redis-backed circuit breaker with OPEN/CLOSED/HALF_OPEN states."""

    def __init__(
        self,
        redis_client,
        domain: str,
        failure_threshold: int = 1,
        recovery_timeout: int = 60,
    ):
        self.redis = redis_client
        self.domain = domain or "unknown"
        self.failure_threshold = int(failure_threshold)
        self.recovery_timeout = int(recovery_timeout)

    @property
    def state_key(self) -> str:
        return f"circuit:{self.domain}:state"

    @property
    def failures_key(self) -> str:
        return f"circuit:{self.domain}:failures"

    @property
    def opened_at_key(self) -> str:
        return f"circuit:{self.domain}:opened_at"

    @staticmethod
    def _decode(value) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore")
        return str(value)

    def _set_with_ttl(self, key: str, value, ttl: int = 300) -> None:
        self.redis.set(key, value)
        self.redis.expire(key, ttl)

    def is_open(self) -> bool:
        state = self._decode(self.redis.get(self.state_key)).upper() or "CLOSED"

        if state == "OPEN":
            opened_at_raw = self._decode(self.redis.get(self.opened_at_key))
            try:
                opened_at = float(opened_at_raw)
            except ValueError:
                opened_at = 0.0

            if (time.time() - opened_at) >= self.recovery_timeout:
                self._set_with_ttl(self.state_key, "HALF_OPEN")
                return False

            return True

        return False

    def record_failure(self, error_type: str):
        failures = self.redis.incr(self.failures_key)
        self.redis.expire(self.failures_key, 300)

        if failures >= self.failure_threshold:
            now_ts = time.time()
            self._set_with_ttl(self.state_key, "OPEN")
            self._set_with_ttl(self.opened_at_key, str(now_ts))
            self.redis.expire(self.failures_key, 300)
            logger.warning("Circuit OPENED for %s (%s)", self.domain, error_type)

    def record_success(self):
        self.redis.delete(self.state_key, self.failures_key, self.opened_at_key)
        logger.info("Circuit CLOSED for %s (recovered)", self.domain)


class CircuitBreaker:
    """Backward-compatible wrapper used by legacy BaseScraper flow."""

    def __init__(self, cooldown_seconds: int = 60):
        self.cooldown_seconds = int(cooldown_seconds)

    def _redis(self):
        backend = getattr(cache, "client", None)
        if backend and hasattr(backend, "get_client"):
            return backend.get_client(write=True)
        raise RuntimeError("Redis cache client is not available for CircuitBreaker")

    def _breaker(self, domain: str) -> RedisCircuitBreaker:
        return RedisCircuitBreaker(
            redis_client=self._redis(),
            domain=domain,
            failure_threshold=1,
            recovery_timeout=self.cooldown_seconds,
        )

    def allow_request(self, domain: str) -> bool:
        return not self._breaker(domain).is_open()

    def record_failure(self, domain: str):
        self._breaker(domain).record_failure("legacy_failure")

    def record_success(self, domain: str):
        self._breaker(domain).record_success()
