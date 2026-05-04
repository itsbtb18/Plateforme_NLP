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

<<<<<<< HEAD
import threading
from datetime import datetime, timedelta

class LLMCircuitBreaker:
    """
    Circuit breaker global pour les providers LLM.
    Si toutes les keys d'un provider retournent 429 dans une fenêtre de 30s,
    met le provider en quarantaine pour 60 minutes.
    """
    
    def __init__(self):
        self._provider_state = {}  # {provider: {"open_until": datetime, "failures": []}}
        self._lock = threading.Lock()
    
    def record_failure(self, provider: str, error_code: int):
        """Appeler après chaque 429. Si plus de 5 échecs en 30s → quarantaine."""
        if error_code != 429:
            return
            
        with self._lock:
            now = datetime.now()
            if provider not in self._provider_state:
                self._provider_state[provider] = {"open_until": None, "failures": []}
            
            state = self._provider_state[provider]
            # Garde seulement les échecs des 30 dernières secondes
            state["failures"] = [f for f in state["failures"] if (now - f).total_seconds() < 30]
            state["failures"].append(now)
            
            # Si plus de 50 échecs en 30s → quarantaine 2 min
            if len(state["failures"]) >= 50:
                state["open_until"] = now + timedelta(minutes=2)
                state["failures"] = []
                logger.warning(f"LLM provider '{provider}' en quarantaine jusqu'à {state['open_until']}")
    
    def is_available(self, provider: str) -> bool:
        """Retourne False si le provider est en quarantaine."""
        with self._lock:
            state = self._provider_state.get(provider)
            if not state or not state["open_until"]:
                return True
            if datetime.now() > state["open_until"]:
                state["open_until"] = None  # Quarantaine expirée
                return True
            return False
    
    def skip_tavily_if_all_down(self) -> bool:
        """Si tous les providers LLM sont down, inutile d'appeler Tavily."""
        providers = ["groq", "gemini"]
        return all(not self.is_available(p) for p in providers)

llm_circuit_breaker = LLMCircuitBreaker()  # Singleton global
=======
    def record_success(self, domain: str):
        self._breaker(domain).record_success()
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
