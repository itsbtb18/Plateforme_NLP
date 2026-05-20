import os
import logging
import time
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import List, Dict, Optional

from django.conf import settings
from django_redis import get_redis_connection

logger = logging.getLogger(__name__)

# Dedicated rotation logger
rotation_logger = logging.getLogger("scraping.api_rotation")
rotation_log_file = os.path.join(settings.BASE_DIR, "scraping", "logs", "api_key_rotations.log")

if not os.path.exists(os.path.dirname(rotation_log_file)):
    os.makedirs(os.path.dirname(rotation_log_file), exist_ok=True)

from dotenv import load_dotenv

# Load environment variables from the parent directory's .env file
env_path = os.path.join(settings.BASE_DIR, "..", ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv() # Fallback to default search

class APIKeyManager:
    """Manages automatic rotation and status tracking of API keys for LLM and Search providers.
    Uses Redis to maintain current index across distributed workers.
    """
    
    def __init__(self):
        self.providers = {
            "groq": self._load_keys("GROQ_API_KEYS"),
            "gemini": self._load_keys("GEMINI_API_KEYS"),
            "tavily": self._load_keys("TAVILY_API_KEYS"),
        }
        try:
            self.redis = get_redis_connection("default")
        except NotImplementedError:
            class FakeRedis:
                def __init__(self):
                    self.store = {}
                def get(self, key):
                    val = self.store.get(key)
                    if val is not None:
                        return str(val).encode('utf-8')
                    return None
                def set(self, key, value):
                    self.store[key] = value
            self.redis = FakeRedis()
        self._ensure_log_exists()
        
        # FIX A: Global circuit breaker per provider
        self._provider_global_failure_until: Dict[str, datetime] = {}
        # Track when each key was last used to detect full cycle failure
        self._cycle_start_time: Dict[str, float] = {}

    def _load_keys(self, env_var: str) -> List[str]:
        keys_str = os.environ.get(env_var, "")
        if not keys_str:
            return []
        return [k.strip() for k in keys_str.split(",") if k.strip()]

    def _ensure_log_exists(self):
        if not os.path.exists(rotation_log_file):
            with open(rotation_log_file, "a") as f:
                f.write(f"# API Key Rotation Log started at {datetime.now()}\n")
                f.write("# timestamp | provider | from_key_index | to_key_index | reason\n")

    def _get_index_key(self, provider: str) -> str:
        return f"api_key_index:{provider}"

    def get_current_index(self, provider: str) -> int:
        idx = self.redis.get(self._get_index_key(provider))
        if idx is None:
            return 0
        return int(idx)

    def get_current_key(self, provider: str) -> Optional[str]:
        # FIX A Check: Global quarantine
        until = self._provider_global_failure_until.get(provider)
        if until and datetime.now() < until:
            remaining = (until - datetime.now()).total_seconds() / 60
            logger.error(f"Provider {provider} in global quarantine for {remaining:.1f} more mins. Skipping.")
            return None

        keys = self.providers.get(provider, [])
        if not keys:
            return None
        idx = self.get_current_index(provider)
        if idx >= len(keys):
            self.redis.set(self._get_index_key(provider), 0)
            idx = 0
        return keys[idx]

    def rotate_key(self, provider: str, reason: str = "rate_limit") -> str:
        keys = self.providers.get(provider, [])
        if not keys:
            return ""
            
        old_idx = self.get_current_index(provider)
        
        # Track cycle timing for FIX A
        if old_idx == 0:
            self._cycle_start_time[provider] = time.time()
            
        new_idx = (old_idx + 1) % len(keys)
        self.redis.set(self._get_index_key(provider), new_idx)
        
        # FIX A: If we rotated back to 0 and the cycle was fast (< 5s), quarantine the provider
        if new_idx == 0 and provider in self._cycle_start_time:
            duration = time.time() - self._cycle_start_time[provider]
            if duration < 5:
                self._provider_global_failure_until[provider] = datetime.now() + timedelta(minutes=1)
                logger.critical(f"Provider {provider} en quarantaine globale pendant 1 min (Full cycle failure in {duration:.1f}s)")

        # Log rotation
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp} | {provider} | {old_idx} | {new_idx} | {reason}\n"
        
        with open(rotation_log_file, "a") as f:
            f.write(log_entry)
            
        logger.warning(f"Rotated {provider} API key from index {old_idx} to {new_idx} due to {reason}")
        return keys[new_idx]

    @contextmanager
    def use_key(self, provider: str):
        """Context manager to automatically rotate key on common rate limit errors."""
        # No delay here

        key = self.get_current_key(provider)
        if not key:
            raise RuntimeError(f"Provider {provider} is currently unavailable (no keys or quarantined)")

        try:
            yield key
        except Exception as exc:
            exc_str = str(exc).lower()
            is_rate_limit = any(s in exc_str for s in ["429", "rate limit", "too many requests", "resourceexhausted"])
            is_quota = any(s in exc_str for s in ["quota", "exhausted", "limit exceeded"])
            
            if is_rate_limit or is_quota:
                reason = "rate_limit" if is_rate_limit else "quota_exceeded"
                
                # No delay here
                if is_rate_limit:
                    logger.warning(f"429 detected for {provider}, rotating immediately...")
                
                self.rotate_key(provider, reason=reason)
                raise
            raise

api_key_manager = APIKeyManager()
