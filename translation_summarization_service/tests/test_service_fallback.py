from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.service import TranslationSummarizationService


class _FailingProvider:
    async def translate(self, **kwargs):
        raise RuntimeError("primary failed")

    async def summarize(self, **kwargs):
        raise RuntimeError("primary failed")


class _WorkingProvider:
    async def translate(self, **kwargs):
        return "fallback-translation"

    async def summarize(self, **kwargs):
        return "fallback-summary"


class _RateLimitedProvider:
    async def translate(self, **kwargs):
        raise RuntimeError("429 Too Many Requests")

    async def summarize(self, **kwargs):
        raise RuntimeError("rate_limit_exceeded")


class _RateLimitThenSuccessProvider:
    def __init__(self, success_output: str = "translated-ok") -> None:
        self.calls = 0
        self.success_output = success_output

    async def translate(self, **kwargs):
        self.calls += 1
        if self.calls < 3:
            raise RuntimeError("429 Too Many Requests")
        return self.success_output


class _CaptureProvider:
    def __init__(self) -> None:
        self.translate_calls: list[dict] = []
        self.summarize_calls: list[dict] = []

    async def translate(self, **kwargs):
        self.translate_calls.append(dict(kwargs))
        return "ok-translation"

    async def summarize(self, **kwargs):
        self.summarize_calls.append(dict(kwargs))
        return "ok-summary"

    async def summarize(self, **kwargs):
        self.calls += 1
        if self.calls < 3:
            raise RuntimeError("rate_limit_exceeded")
        return self.success_output


class _FakeRedisCache:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def get(self, key: str):
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value: str):
        _ = ttl
        self.store[key] = value


class _AsyncFakeRedisQueue:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.lists: dict[str, list[str]] = {}
        self.expirations: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        value = int(self.values.get(key, "0")) + 1
        self.values[key] = str(value)
        return value

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value, ex: int | None = None):
        self.values[key] = str(value)
        if ex is not None:
            self.expirations[key] = ex

    async def setex(self, key: str, ttl: int, value):
        self.values[key] = str(value)
        self.expirations[key] = ttl

    async def delete(self, *keys: str):
        for key in keys:
            self.values.pop(key, None)
            self.hashes.pop(key, None)
            self.lists.pop(key, None)
            self.expirations.pop(key, None)

    async def expire(self, key: str, ttl: int):
        self.expirations[key] = ttl

    async def hgetall(self, key: str):
        return dict(self.hashes.get(key, {}))

    async def hset(self, key: str, mapping: dict[str, str]):
        bucket = self.hashes.setdefault(key, {})
        bucket.update({k: str(v) for k, v in mapping.items()})

    async def rpush(self, key: str, value: str) -> int:
        items = self.lists.setdefault(key, [])
        items.append(value)
        return len(items)

    async def lindex(self, key: str, index: int):
        items = self.lists.get(key, [])
        try:
            return items[index]
        except IndexError:
            return None

    async def lrem(self, key: str, count: int, value: str):
        items = self.lists.get(key, [])
        removed = 0
        remaining: list[str] = []
        for item in items:
            if item == value and (count == 0 or removed < count):
                removed += 1
                continue
            remaining.append(item)
        self.lists[key] = remaining
        return removed

    async def llen(self, key: str):
        return len(self.lists.get(key, []))


def test_provider_order_from_env(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "gemini")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "groq")

    from app.config import get_settings

    get_settings.cache_clear()
    svc = TranslationSummarizationService()
    assert svc.provider_order() == ["gemini", "groq"]


def test_translate_uses_fallback(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "gemini")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "groq")

    from app.config import get_settings

    get_settings.cache_clear()
    svc = TranslationSummarizationService()
    svc.providers = {"gemini": _FailingProvider(), "groq": _WorkingProvider()}

    output, provider, fallback = _run_async(
        svc.translate(text="bonjour", source_language="fr", target_language="en")
    )

    assert output
    assert provider == "groq"
    assert fallback is True


def test_translate_normalizes_language_aliases(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "gemini")

    from app.config import get_settings

    get_settings.cache_clear()
    svc = TranslationSummarizationService()
    capture = _CaptureProvider()
    svc.providers = {"gemini": _FailingProvider(), "groq": capture}
    svc.cache_client = _AsyncFakeRedisQueue()

    output, provider, fallback = _run_async(
        svc.translate(text="Bonjour tout le monde", source_language="french", target_language="arabic")
    )

    assert output == "ok-translation"
    assert provider == "groq"
    assert fallback is False
    assert capture.translate_calls
    assert capture.translate_calls[0]["source_language"] == "fr"
    assert capture.translate_calls[0]["target_language"] == "ar"


def test_summarize_auto_language_uses_text_inference(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "gemini")

    from app.config import get_settings

    get_settings.cache_clear()
    svc = TranslationSummarizationService()
    capture = _CaptureProvider()
    svc.providers = {"gemini": _FailingProvider(), "groq": capture}
    svc.cache_client = _AsyncFakeRedisQueue()

    output, provider, fallback = _run_async(
        svc.summarize(
            text="هذا نص عربي للاختبار. يحتوي على جمل متعددة لاختبار كشف اللغة.",
            language="auto",
            style="brief",
            max_words=120,
        )
    )

    assert output
    assert provider == "groq"
    assert fallback is False
    assert capture.summarize_calls
    assert capture.summarize_calls[0]["language"] == "ar"


def test_summarize_uses_primary(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "gemini")

    from app.config import get_settings

    get_settings.cache_clear()
    svc = TranslationSummarizationService()
    svc.providers = {"gemini": _FailingProvider(), "groq": _WorkingProvider()}

    output, provider, fallback = _run_async(
        svc.summarize(text="Long text", language="en", style="brief", max_words=120)
    )

    assert "fallback-summary" in output
    assert "# Document" not in output
    assert provider == "groq"
    assert fallback is False


def test_translate_uses_local_fallback_on_rate_limit(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "gemini")

    from app.config import get_settings

    get_settings.cache_clear()

    svc = TranslationSummarizationService()
    svc.providers = {"gemini": _RateLimitedProvider(), "groq": _WorkingProvider()}

    output, provider, fallback = _run_async(
        svc.translate(text="bonjour le monde", source_language="fr", target_language="en")
    )

    assert output == "fallback-translation"
    assert provider == "groq"
    assert fallback is False


def test_summarize_uses_local_fallback_when_providers_fail(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "gemini")

    from app.config import get_settings

    get_settings.cache_clear()
    svc = TranslationSummarizationService()
    svc.providers = {"gemini": _FailingProvider(), "groq": _FailingProvider()}
    svc.cache_client = _AsyncFakeRedisQueue()

    text = (
        "This is the first important sentence. "
        "This is the second important sentence with more details. "
        "This section continues with relevant context for the summary."
    )

    output, provider, fallback = _run_async(
        svc.summarize(text=text, language="en", style="brief", max_words=80)
    )

    assert output
    assert "important sentence" in output.lower()
    assert provider == "local"
    assert fallback is True


def test_translate_skips_rate_limited_provider_during_cooldown(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "gemini")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "groq")
    monkeypatch.setenv("TS_RATE_LIMIT_MAX_RETRIES", "0")

    from app.config import get_settings
    import app.service as service_module

    get_settings.cache_clear()

    current_time = {"value": 100.0}

    def fake_monotonic() -> float:
        return current_time["value"]

    monkeypatch.setattr(service_module.time, "monotonic", fake_monotonic)

    svc = TranslationSummarizationService()
    svc.cache_client = _AsyncFakeRedisQueue()
    svc.providers = {"gemini": _RateLimitedProvider(), "groq": _WorkingProvider()}

    first = _run_async(
        svc.translate(text="bonjour le monde", source_language="fr", target_language="en")
    )
    second = _run_async(
        svc.translate(text="bonjour le monde encore", source_language="fr", target_language="en")
    )

    assert first[0] == "fallback-translation"
    assert first[1] == "groq"
    assert second[0] == "fallback-translation"
    assert second[1] == "groq"
    assert svc._provider_cooldown_remaining("gemini") > 0


def test_resolve_translation_chunk_size_uses_smaller_chunks_for_other_languages(monkeypatch):
    monkeypatch.setenv("TS_TRANSLATION_CHUNK_SIZE", "3200")

    from app.config import get_settings

    get_settings.cache_clear()

    svc = TranslationSummarizationService()

    assert svc._resolve_translation_chunk_size(
        source_language="de",
        target_language="ar",
        text="x" * 14000,
    ) == 2400


def test_translate_uses_google_fallback_when_providers_fail(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "gemini")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "groq")

    from app.config import get_settings
    import app.service as service_module

    get_settings.cache_clear()

    async def fake_google_fallback(self, *, text: str, source_language: str, target_language: str):
        _ = (text, source_language, target_language)
        return "google-translation"

    monkeypatch.setattr(
        service_module.TranslationSummarizationService,
        "_translate_with_google_fallback",
        fake_google_fallback,
    )

    svc = TranslationSummarizationService()
    svc.providers = {"gemini": _FailingProvider(), "groq": _FailingProvider()}
    svc.cache_client = _AsyncFakeRedisQueue()

    output, provider, fallback = _run_async(
        svc.translate(text="bonjour le monde", source_language="fr", target_language="en")
    )

    assert output == "google-translation"
    assert provider == "google"
    assert fallback is True


def test_google_fallback_uses_smaller_chunk_size(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "gemini")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "groq")

    from app.config import get_settings
    import app.service as service_module

    get_settings.cache_clear()

    observed: list[int] = []

    def fake_split_translation_chunks(self, *, text: str, source_language: str, target_language: str, max_chars: int | None = None):
        _ = (source_language, target_language)
        observed.append(max_chars)
        return [text, text]

    def fake_google_translate_chunk(text: str, source_language: str, target_language: str) -> str:
        _ = (source_language, target_language)
        return f"translated:{text}"

    monkeypatch.setattr(
        service_module.TranslationSummarizationService,
        "_split_translation_chunks",
        fake_split_translation_chunks,
    )
    monkeypatch.setattr(
        service_module.TranslationSummarizationService,
        "_google_translate_chunk",
        staticmethod(fake_google_translate_chunk),
    )

    svc = TranslationSummarizationService()
    svc.providers = {"gemini": _FailingProvider(), "groq": _FailingProvider()}

    output = _run_async(
        svc._translate_with_google_fallback(
            text="bonjour le monde",
            source_language="fr",
            target_language="en",
        )
    )

    assert output == "translated:bonjour le monde\n\ntranslated:bonjour le monde"
    assert observed and observed[0] == svc.google_fallback_chunk_size


def test_translate_uses_cache_on_repeat_request(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "gemini")

    from app.config import get_settings

    get_settings.cache_clear()

    svc = TranslationSummarizationService()
    svc.providers = {"gemini": _FailingProvider(), "groq": _WorkingProvider()}
    svc.cache_client = _FakeRedisCache()

    first = _run_async(svc.translate(text="bonjour le monde", source_language="fr", target_language="en"))
    second = _run_async(svc.translate(text="bonjour le monde", source_language="fr", target_language="en"))

    assert first[0] == "fallback-translation"
    assert second[0] == "fallback-translation"
    assert first[1] == "groq"
    assert second[1] == "cache"


def test_translate_falls_back_without_long_retry(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "gemini")

    from app.config import get_settings
    import app.service as service_module

    get_settings.cache_clear()

    sleeps: list[float] = []

    async def fake_sleep(seconds: float):
        sleeps.append(seconds)

    monkeypatch.setattr(service_module.asyncio, "sleep", fake_sleep)

    svc = TranslationSummarizationService()
    svc.providers = {"gemini": _FailingProvider(), "groq": _RateLimitThenSuccessProvider()}
    svc.cache_client = _FakeRedisCache()

    output, provider_used, fallback = _run_async(
        svc.translate(text="bonjour le monde", source_language="fr", target_language="en")
    )

    assert output == "translated-ok"
    assert provider_used == "groq"
    assert fallback is False
    assert sleeps


def test_translate_reuses_chunk_cache(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "gemini")

    from app.config import get_settings

    get_settings.cache_clear()

    svc = TranslationSummarizationService()
    svc.cache_client = _FakeRedisCache()
    import app.service as service_module
    monkeypatch.setattr(service_module.TranslationSummarizationService, "_split_into_chunks", lambda self, text, max_chars=5200: ["Same phrase", "Same phrase"])
    svc.providers = {"gemini": _FailingProvider(), "groq": _WorkingProvider()}

    first = _run_async(svc.translate(text="Same phrase\n\nSame phrase", source_language="fr", target_language="en"))
    second = _run_async(svc.translate(text="Same phrase\n\nSame phrase", source_language="fr", target_language="en"))

    assert first[0]
    assert second[0]
    assert first[0] == second[0]
    assert first[1] == "groq"
    assert second[1] == "cache"
    assert first[2] is False
    assert second[2] is False


def test_provider_rate_limit_sets_short_cooldown(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    svc = TranslationSummarizationService()
    svc.cache_client = _AsyncFakeRedisQueue()

    first = _run_async(svc._record_provider_rate_limit("gemini"))
    second = _run_async(svc._record_provider_rate_limit("gemini"))

    assert first == 0
    assert second == 60
    assert svc.cache_client.values["ts:provider:gemini:cooldown"] == "60"


def test_user_queue_waits_for_refill_and_keeps_fifo(monkeypatch):
    monkeypatch.setenv("TS_RATE_LIMIT_BUCKET_CAPACITY", "1")
    monkeypatch.setenv("TS_RATE_LIMIT_REFILL_WINDOW_SECONDS", "60")

    from app.config import get_settings

    get_settings.cache_clear()
    svc = TranslationSummarizationService()
    svc.cache_client = _AsyncFakeRedisQueue()

    clock = {"now": 0.0}
    sleeps: list[float] = []

    monkeypatch.setattr("app.service.time.time", lambda: clock["now"])

    async def fake_sleep(seconds: float):
        sleeps.append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr("app.service.asyncio.sleep", fake_sleep)

    async def run() -> tuple[float, float, str]:
        await svc._wait_for_request_slot("alice")
        first = clock["now"]
        await svc._wait_for_request_slot("alice")
        second = clock["now"]
        scope = svc._user_scope("alice")
        head = svc.cache_client.values[f"ts:queue:{scope}:head"]
        return first, second, head

    first_time, second_time, head_value = _run_async(run())

    assert first_time == 0.0
    assert second_time >= 59.9
    assert head_value == "3"
    assert any(delay > 0 for delay in sleeps)


def test_users_do_not_block_each_other(monkeypatch):
    monkeypatch.setenv("TS_RATE_LIMIT_BUCKET_CAPACITY", "1")
    monkeypatch.setenv("TS_RATE_LIMIT_REFILL_WINDOW_SECONDS", "60")

    from app.config import get_settings

    get_settings.cache_clear()
    svc = TranslationSummarizationService()
    svc.cache_client = _AsyncFakeRedisQueue()

    clock = {"now": 0.0}
    monkeypatch.setattr("app.service.time.time", lambda: clock["now"])

    async def fake_sleep(seconds: float):
        clock["now"] += seconds

    monkeypatch.setattr("app.service.asyncio.sleep", fake_sleep)

    async def run() -> tuple[float, float]:
        await svc._wait_for_request_slot("alice")
        first = clock["now"]
        await svc._wait_for_request_slot("bob")
        second = clock["now"]
        return first, second

    first_time, second_time = _run_async(run())

    assert first_time == 0.0
    assert second_time == 0.0


def test_user_queue_rejects_overflow(monkeypatch):
    monkeypatch.setenv("TS_QUEUE_MAX_SIZE_PER_USER", "2")

    from app.config import get_settings

    get_settings.cache_clear()
    svc = TranslationSummarizationService()
    cache = _AsyncFakeRedisQueue()
    svc.cache_client = cache

    scope = svc._user_scope("alice")
    cache.values[f"ts:queue:{scope}:seq"] = "10"
    cache.values[f"ts:queue:{scope}:head"] = "1"

    async def run():
        await svc._wait_for_request_slot("alice")

    import pytest

    with pytest.raises(RuntimeError, match="Too many requests in queue for this user"):
        _run_async(run())


def test_translate_allows_only_one_active_request_globally(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "gemini")

    from app.config import get_settings

    get_settings.cache_clear()
    svc = TranslationSummarizationService()
    svc.cache_client = _AsyncFakeRedisQueue()
    svc.global_min_interval_seconds = 0.0

    async def fake_slot():
        return None

    svc._await_global_request_slot = fake_slot

    active = 0
    peak = 0
    first_started = asyncio.Event()
    release_first = asyncio.Event()

    class _BlockingProvider:
        async def translate(self, **kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            first_started.set()
            await release_first.wait()
            active -= 1
            return "ok"

        async def summarize(self, **kwargs):
            return "ok"

    svc.providers = {"gemini": _BlockingProvider(), "groq": _BlockingProvider()}

    async def run() -> tuple[str, str]:
        task1 = asyncio.create_task(svc.translate(text="bonjour", source_language="fr", target_language="en"))
        await first_started.wait()
        task2 = asyncio.create_task(svc.translate(text="salut", source_language="fr", target_language="en"))
        await asyncio.sleep(0)
        release_first.set()
        result1 = await task1
        result2 = await task2
        return result1[0], result2[0]

    result1, result2 = _run_async(run())

    assert result1 == "ok"
    assert result2 == "ok"
    assert peak == 1


def test_summarize_uses_local_fallback_on_rate_limit(monkeypatch):
    monkeypatch.setenv("TS_PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("TS_FALLBACK_PROVIDER", "gemini")

    from app.config import get_settings

    get_settings.cache_clear()
    svc = TranslationSummarizationService()
    svc.providers = {"gemini": _RateLimitedProvider(), "groq": _RateLimitedProvider()}

    text = (
        "First part explains the project scope and main objectives. "
        "Second part details constraints and implementation decisions. "
        "Third part presents expected outcomes and evaluation criteria."
    )
    output, provider, fallback = _run_async(
        svc.summarize(text=text, language="en", style="professional", max_words=120)
    )

    assert output
    assert provider == "local-fallback"
    assert fallback is True


def _run_async(coro):
    import asyncio

    return asyncio.run(coro)
