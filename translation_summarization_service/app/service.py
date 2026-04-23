from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import re
import time
import uuid
from typing import Awaitable, Callable

from redis.asyncio import Redis

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except Exception:  # pragma: no cover - optional dependency fallback at runtime
    RecursiveCharacterTextSplitter = None

from app.config import get_settings
from app.providers.gemini_provider import GeminiProvider
from app.providers.groq_provider import GroqProvider


logger = logging.getLogger(__name__)

INSTANCE_ID = uuid.uuid4().hex[:8]


class TranslationSummarizationService:
    DEFAULT_CHUNK_SIZE = 5200
    DEFAULT_CHUNK_OVERLAP = 200
    MAX_TRANSLATION_CHUNKS_PER_DOCUMENT = 3
    GLOBAL_REQUESTS_PER_MINUTE = 10
    GLOBAL_MIN_INTERVAL_SECONDS = 6.0
    MAX_TRANSLATION_CHUNKS_PER_DOCUMENT = 3
    CACHE_NAMESPACE_TRANSLATION = "ts:translation"
    CACHE_NAMESPACE_TRANSLATION_CHUNK = "ts:translation:chunk"
    CACHE_NAMESPACE_SUMMARY = "ts:summary"
    GLOBAL_MUTEX_KEY = "ts:scheduler:mutex"
    GLOBAL_MUTEX_TTL = 60  # Reduced for faster recovery if worker dies
    GLOBAL_NEXT_ALLOWED_AT_KEY = "ts:scheduler:next_allowed_at"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.instance_id = INSTANCE_ID
        self.providers = {
            "gemini": GeminiProvider(),
            "groq": GroqProvider(),
        }
        self.cache_client = self._build_cache_client()
        self.global_min_interval_seconds = self._resolve_global_min_interval_seconds()
        logger.info("TS Service initialized instance_id=%s", self.instance_id)

    def _resolve_global_min_interval_seconds(self) -> float:
        rpm = max(1, int(getattr(self.settings, "TS_GLOBAL_REQUESTS_PER_MINUTE", self.GLOBAL_REQUESTS_PER_MINUTE)))
        derived = 60.0 / float(rpm)
        configured = float(getattr(self.settings, "TS_GLOBAL_MIN_INTERVAL_SECONDS", self.GLOBAL_MIN_INTERVAL_SECONDS))
        return max(derived, configured, 1.0)

    def provider_order(self) -> list[str]:
        primary = self.settings.TS_PRIMARY_PROVIDER.strip().lower()
        fallback = self.settings.TS_FALLBACK_PROVIDER.strip().lower()

        valid = {"gemini", "groq"}
        if primary not in valid:
            primary = "gemini"
        if fallback not in valid or fallback == primary:
            fallback = "groq" if primary == "gemini" else "gemini"

        return [primary, fallback]

    async def translate(
        self,
        *,
        text: str,
        source_language: str,
        target_language: str,
        user_id: str | None = None,
    ) -> tuple[str, str, bool]:
        prepared_text = self._prepare_text_for_translation(text)
        self._log_request_start("translation", user_id, prepared_text)
        cache_key = self._cache_key(
            task="translation",
            text=prepared_text,
            source_language=source_language,
            target_language=target_language,
        )
        request_id = f"{self.instance_id}:{uuid.uuid4().hex[:8]}"
        try:
            await self._wait_for_request_slot(user_id, request_id)
            async with await self._global_mutex():
                output, provider_used, fallback_used = await self._translate_via_providers(
                    text=prepared_text,
                    source_language=source_language,
                    target_language=target_language,
                    user_id=user_id,
                )
                await self._cache_set(self.CACHE_NAMESPACE_TRANSLATION, cache_key, output)
                logger.info(
                    "TS request done task=translation provider=%s user=%s text=%s instance=%s",
                    provider_used,
                    self._safe_log_user(user_id),
                    self._safe_log_text(prepared_text),
                    self.instance_id,
                )
                return output, provider_used, fallback_used
        finally:
            await self._release_request_slot(user_id, request_id)

    async def _translate_via_providers(
        self,
        *,
        text: str,
        source_language: str,
        target_language: str,
        user_id: str | None = None,
    ) -> tuple[str, str, bool]:
        chunks = self._split_into_chunks(text)
        chunks = self._rebalance_chunks(chunks, max_chunks=self.MAX_TRANSLATION_CHUNKS_PER_DOCUMENT)
        order = self.provider_order()
        errors: list[str] = []

        for idx, name in enumerate(order):
            provider = self.providers[name]
            translated_chunks: list[str] = []
            provider_errors: list[str] = []
            for i, chunk in enumerate(chunks):
                chunk_key = self._cache_key(
                    task="translation-chunk",
                    text=chunk,
                    source_language=source_language,
                    target_language=target_language,
                )
                cached_chunk = await self._cache_get(self.CACHE_NAMESPACE_TRANSLATION_CHUNK, chunk_key)
                if cached_chunk:
                    translated_chunks.append(cached_chunk)
                    continue

                translated_piece: str | None = None
                try:
                    translated_piece = await self._call_with_rate_limit_retry(
                        provider_name=name,
                        user_id=user_id,
                        chunk_id=f"chunk_{i}",
                        max_retries=2,
                        op=lambda c=chunk: provider.translate(
                            text=c,
                            source_language=source_language,
                            target_language=target_language,
                        ),
                    )
                    translated_piece = self._post_process_translation(translated_piece)
                    if self._looks_like_summary(source_text=chunk, translated_text=translated_piece):
                        raise RuntimeError("provider output looks summarized/compressed, not full translation")
                except Exception as exc:
                    provider_errors.append(self._sanitize_error_message(str(exc)))
                    translated_piece = None

                if translated_piece:
                    await self._cache_set(self.CACHE_NAMESPACE_TRANSLATION_CHUNK, chunk_key, translated_piece)
                    translated_chunks.append(translated_piece)

                if i < len(chunks) - 1 and self.global_min_interval_seconds > 0:
                    await asyncio.sleep(self.global_min_interval_seconds)

            if not translated_chunks:
                errors.append(f"{name}: " + " | ".join(provider_errors) if provider_errors else f"{name}: translation failed")
                continue

            output = self._merge_chunks(translated_chunks)
            if self._looks_like_summary(source_text=text, translated_text=output):
                raise RuntimeError("provider output looks summarized/compressed, not full translation")

            return output, name, idx > 0

        raise RuntimeError("All providers failed: " + " | ".join(errors))

    async def summarize(
        self,
        *,
        text: str,
        language: str,
        style: str,
        max_words: int | None,
        user_id: str | None = None,
    ) -> tuple[str, str, bool]:
        errors: list[str] = []
        prepared_text = self._prepare_text_for_summarization(text)
        self._log_request_start("summarization", user_id, prepared_text)
        cache_key = self._cache_key(
            task="summary",
            text=prepared_text,
            language=language,
            style=style,
            max_words=max_words,
        )
        cached_output = await self._cache_get(self.CACHE_NAMESPACE_SUMMARY, cache_key)
        if cached_output:
            logger.info("TS cache hit task=summarization user=%s text=%s", self._safe_log_user(user_id), self._safe_log_text(prepared_text))
            return cached_output, "cache", False

        request_id = f"{self.instance_id}:{uuid.uuid4().hex[:8]}"
        try:
            await self._wait_for_request_slot(user_id, request_id)
            async with await self._global_mutex():
                    sections = self._split_into_sections(prepared_text)
                    sections = self._rebalance_sections(sections, max_sections=3)
                    order = self.provider_order()
                    for idx, name in enumerate(order):
                        provider = self.providers[name]
                        try:
                            summarized_sections: list[dict[str, str | int]] = []
                            for section in sections:
                                section_title = str(section["title"])
                                section_level = int(section["level"])
                                section_body = str(section["content"]).strip() or section_title

                                section_target_words = self._estimate_section_summary_words(len(section_body.split()), max_words)
                                section_summary = await self._call_with_rate_limit_retry(
                                    provider_name=name,
                                    user_id=user_id,
                                    chunk_id=f"section_{section_title[:20]}",
                                    op=lambda body=section_body, w=section_target_words: provider.summarize(
                                        text=body,
                                        language=language,
                                        style=f"section::{style}",
                                        max_words=w,
                                    ),
                                )
                                section_summary = self._post_process_summary(section_summary)

                                summarized_sections.append(
                                    {
                                        "title": section_title,
                                        "level": section_level,
                                        "summary": section_summary,
                                    }
                                )
                                
                                if sections.index(section) < len(sections) - 1 and self.global_min_interval_seconds > 0:
                                    logger.info("TS summarization pacing between sections: %.2fs", self.global_min_interval_seconds)
                                    await asyncio.sleep(self.global_min_interval_seconds)

                            output = self._render_structured_summary(summarized_sections)
                            await self._cache_set(self.CACHE_NAMESPACE_SUMMARY, cache_key, output)
                            logger.info(
                                "TS request done task=summarization provider=%s user=%s text=%s instance=%s",
                                name,
                                self._safe_log_user(user_id),
                                self._safe_log_text(prepared_text),
                                self.instance_id,
                            )
                            return output, name, idx > 0
                        except Exception as exc:
                            safe_error = self._sanitize_error_message(str(exc))
                            errors.append(f"{name}: {safe_error}")
                            continue
        finally:
            await self._release_request_slot(user_id, request_id)

        raise RuntimeError("All providers failed: " + " | ".join(errors))

    async def chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        provider_name: str | None = None,
        user_id: str | None = None,
    ) -> tuple[str, str, bool]:
        order = [provider_name] if provider_name in self.providers else self.provider_order()
        errors: list[str] = []

        request_id = f"{self.instance_id}:{uuid.uuid4().hex[:8]}"
        try:
            await self._wait_for_request_slot(user_id, request_id)
            async with await self._global_mutex():
                for idx, name in enumerate(order):
                    provider = self.providers[name]
                    try:
                        output = await self._call_with_rate_limit_retry(
                            provider_name=name,
                            user_id=user_id,
                            chunk_id="chat",
                            op=lambda: provider._generate(prompt=f"{system_prompt}\n\n{user_prompt}", model=getattr(provider, "model_translate", "auto")),
                        )
                        return output, name, idx > 0
                    except Exception as exc:
                        errors.append(f"{name}: {self._sanitize_error_message(str(exc))}")
                        continue
        finally:
            await self._release_request_slot(user_id, request_id)

        raise RuntimeError("Chat failed: " + " | ".join(errors))

    @staticmethod
    def _sanitize_error_message(message: str) -> str:
        text = str(message or "")
        # Remove credential-like query params that may appear in upstream URLs.
        text = re.sub(r"([?&](?:key|api_key|token)=)[^&\s]+", r"\1***", text, flags=re.IGNORECASE)
        return text

    async def _call_with_rate_limit_retry(
        self,
        *,
        provider_name: str,
        op: Callable[[], Awaitable[str]],
        user_id: str | None = None,
        chunk_id: str | None = None,
        max_retries: int | None = None,
    ) -> str:
        # Increase retries for better resilience against provider rate limits
        max_retries = max(0, min(5, int(getattr(self.settings, "TS_RATE_LIMIT_MAX_RETRIES", 4) if max_retries is None else max_retries)))
        base_delay = max(10.0, float(self.settings.TS_RATE_LIMIT_BASE_DELAY_SECONDS))
        max_wait = min(60.0, max(base_delay, float(self.settings.TS_RATE_LIMIT_MAX_WAIT_SECONDS)))

        logger.info(
            "TS AI call start provider=%s user=%s chunk=%s instance=%s",
            provider_name,
            self._safe_log_user(user_id),
            chunk_id or "root",
            self.instance_id,
        )

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                await self._await_global_request_slot()
                result = await op()
                logger.info(
                    "TS AI call success provider=%s user=%s chunk=%s attempt=%s instance=%s",
                    provider_name,
                    self._safe_log_user(user_id),
                    chunk_id or "root",
                    attempt + 1,
                    self.instance_id,
                )
                return result
            except Exception as exc:
                last_exc = exc
                if not self._is_rate_limit_error(exc):
                    logger.warning(
                        "TS AI call failed provider=%s user=%s chunk=%s attempt=%s reason=%s instance=%s",
                        provider_name,
                        self._safe_log_user(user_id),
                        chunk_id or "root",
                        attempt + 1,
                        self._sanitize_error_message(str(exc)),
                        self.instance_id,
                    )
                    raise

                if attempt >= max_retries:
                    break

                advised_wait = self._extract_retry_after_seconds(str(exc))
                if advised_wait is not None and advised_wait > max_wait:
                    advised_wait = max_wait

                wait_seconds = advised_wait if advised_wait is not None else min(max_wait, base_delay * (2 ** attempt))
                wait_seconds = max(10.0, min(wait_seconds, max_wait))
                
                logger.info(
                    "TS AI rate limit retry provider=%s user=%s chunk=%s attempt=%s waiting=%.2fs instance=%s",
                    provider_name,
                    self._safe_log_user(user_id),
                    chunk_id or "root",
                    attempt + 1,
                    wait_seconds,
                    self.instance_id,
                )
                
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

        message = self._sanitize_error_message(str(last_exc)) if last_exc else "rate limit"
        raise RuntimeError(f"Rate limit persisted for provider {provider_name}: {message}")

    @staticmethod
    def _is_rate_limit_error(exc: Exception) -> bool:
        msg = str(exc or "").lower()
        return (
            "rate limit" in msg
            or "too many requests" in msg
            or "429" in msg
            or "rate_limit_exceeded" in msg
        )

    @staticmethod
    def _extract_retry_after_seconds(message: str) -> float | None:
        text = str(message or "")

        # Examples:
        # - "Please try again in 2.24s"
        # - "Please try again in 14m30.912s"
        mix = re.search(r"try again in\s*(?:(\d+)m)?\s*(\d+(?:\.\d+)?)s", text, flags=re.IGNORECASE)
        if mix:
            mins = float(mix.group(1) or 0)
            secs = float(mix.group(2) or 0)
            return (mins * 60.0) + secs

        sec_only = re.search(r"retry after\s*(\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
        if sec_only:
            return float(sec_only.group(1))

        return None

    @classmethod
    def _all_errors_rate_limited(cls, errors: list[str]) -> bool:
        if not errors:
            return False
        return all(cls._is_rate_limit_error(RuntimeError(err)) for err in errors)

    @staticmethod
    def _local_section_summary(text: str, *, target_words: int) -> str:
        source = re.sub(r"\s+", " ", str(text or "")).strip()
        if not source:
            return ""

        # Keep a concise multi-sentence extract to provide continuity when APIs are throttled.
        sentences = [s.strip() for s in re.split(r"(?<=[\.!?؟])\s+", source) if s.strip()]
        if not sentences:
            return source[:360]

        max_words = max(120, min(600, int(target_words or 240)))
        selected: list[str] = []
        words_used = 0

        for sentence in sentences:
            count = len(sentence.split())
            if selected and words_used + count > max_words:
                break
            selected.append(sentence)
            words_used += count
            if words_used >= max_words:
                break

        if not selected:
            return sentences[0]
        return " ".join(selected).strip()

    @staticmethod
    def _looks_like_summary(*, source_text: str, translated_text: str) -> bool:
        source = (source_text or "").strip()
        output = (translated_text or "").strip()
        if not source or not output:
            return True

        src_words = len(source.split())
        out_words = len(output.split())
        ratio = out_words / max(src_words, 1)

        if src_words >= 120 and ratio < 0.45:
            return True

        lower_output = output.lower()
        summary_markers = [
            "executive summary",
            "section summaries",
            "key points",
            "key conclusions",
            "in summary",
            "summary:",
        ]
        if any(marker in lower_output for marker in summary_markers):
            return True

        src_non_empty_lines = len([ln for ln in re.split(r"\r?\n", source) if ln.strip()])
        out_non_empty_lines = len([ln for ln in re.split(r"\r?\n", output) if ln.strip()])
        if src_non_empty_lines >= 20 and out_non_empty_lines < max(5, src_non_empty_lines // 4):
            return True

        return False

    @staticmethod
    def _prepare_text_for_translation(text: str) -> str:
        prepared = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        # Fix soft hyphenation and noisy spacing from PDF extraction.
        prepared = re.sub(r"(?<=\w)-\n(?=\w)", "", prepared)
        prepared = re.sub(r"[ \t]+", " ", prepared)
        prepared = re.sub(r"\n{3,}", "\n\n", prepared)
        return prepared.strip()

    @classmethod
    def _prepare_text_for_summarization(cls, text: str) -> str:
        """Reuse translation preparation logic for summarization."""
        return cls._prepare_text_for_translation(text)

    def _build_cache_client(self) -> Redis | None:
        try:
            client = Redis.from_url(
                self.settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
            return client
        except Exception as exc:
            logger.error("Failed to initialize Redis client for TS Service: %s", exc)
            return None

    @staticmethod
    async def _await_redis(value):
        if inspect.isawaitable(value):
            return await value
        return value

    @staticmethod
    def _cache_key(*, task: str, text: str, **metadata: object) -> str:
        payload = {"task": task, "text": text, **metadata}
        serialised = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialised.encode("utf-8")).hexdigest()

    async def _cache_get(self, namespace: str, key: str) -> str | None:
        if not self.cache_client:
            return None
        try:
            raw = await self._await_redis(self.cache_client.get(f"{namespace}:{key}"))
            if not raw:
                return None
            data = json.loads(raw)
            output = str(data.get("output") or "").strip()
            return output or None
        except Exception:
            return None

    async def _cache_set(self, namespace: str, key: str, output: str) -> None:
        if not self.cache_client:
            return
        try:
            await self._await_redis(self.cache_client.setex(
                f"{namespace}:{key}",
                max(60, int(self.settings.TS_CACHE_TTL_SECONDS)),
                json.dumps({"output": output}, ensure_ascii=False),
            ))
        except Exception:
            return

    @staticmethod
    def _user_scope(user_id: str | None) -> str:
        source = str(user_id or "anonymous").strip() or "anonymous"
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        return digest[:32]

    async def _wait_for_request_slot(self, user_id: str | None, request_id: str) -> int:
        if not self.cache_client:
            return 1

        user_scope = self._user_scope(user_id)
        queue_key = f"ts:queue:{user_scope}:list"

        try:
            # Add this request to the end of the user's FIFO queue
            queue_len = await self._await_redis(self.cache_client.rpush(queue_key, request_id))
            await self._await_redis(self.cache_client.expire(queue_key, 600))

            max_queue_size = max(1, int(self.settings.TS_QUEUE_MAX_SIZE_PER_USER))
            if queue_len > max_queue_size:
                logger.warning("TS queue overflow user=%s queue_size=%s", self._safe_log_user(user_id), queue_len)
                # Cleanup if we overflow
                await self._await_redis(self.cache_client.lrem(queue_key, 0, request_id))
                raise RuntimeError("Too many requests in queue for this user")

            # Wait until this request is at the front of the list
            start_time = time.time()
            while True:
                # Check for timeout (safety net)
                if time.time() - start_time > 300: # 5 min max wait
                    raise RuntimeError("Queue wait timeout")

                head = await self._await_redis(self.cache_client.lindex(queue_key, 0))
                if head == request_id:
                    # It's our turn
                    return int(queue_len)
                
                # Still waiting
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            # IMPORTANT: If the request is closed/cancelled, remove it from the queue
            # so the next one can proceed immediately.
            logger.info("TS request cancelled while in queue user=%s request_id=%s", self._safe_log_user(user_id), request_id)
            await self._await_redis(self.cache_client.lrem(queue_key, 0, request_id))
            raise
        except Exception as exc:
            # Cleanup on other errors
            await self._await_redis(self.cache_client.lrem(queue_key, 0, request_id))
            raise

    async def _release_request_slot(self, user_id: str | None, request_id: str) -> None:
        """Explicitly release the head of the queue after the request is processed."""
        if not self.cache_client:
            return
        user_scope = self._user_scope(user_id)
        queue_key = f"ts:queue:{user_scope}:list"
        try:
            # We only pop if we are actually at the head
            head = await self._await_redis(self.cache_client.lindex(queue_key, 0))
            if head == request_id:
                await self._await_redis(self.cache_client.lpop(queue_key))
        except Exception:
            pass

    async def _await_global_request_slot(self) -> None:
        interval = max(1.0, float(self.global_min_interval_seconds))
        now = time.time()

        if not self.cache_client:
            await asyncio.sleep(interval)
            return

        try:
            raw_next_allowed = await self._await_redis(self.cache_client.get(self.GLOBAL_NEXT_ALLOWED_AT_KEY))
            next_allowed_at = float(raw_next_allowed) if raw_next_allowed else now
            wait_seconds = max(0.0, next_allowed_at - now)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)

            current = time.time()
            next_slot = max(current, next_allowed_at) + interval
            await self._await_redis(self.cache_client.set(self.GLOBAL_NEXT_ALLOWED_AT_KEY, str(next_slot), ex=3600))
            logger.info("TS pacing instance=%s wait=%.2fs", self.instance_id, wait_seconds)
        except Exception:
            await asyncio.sleep(interval)

    async def _global_mutex(self):
        if not self.cache_client:
            return _NullAsyncContext()

        if not all(hasattr(self.cache_client, attr) for attr in ("set", "get", "delete")):
            return _NullAsyncContext()

        token = f"{self.instance_id}:{uuid.uuid4().hex}"
        lock_key = self.GLOBAL_MUTEX_KEY
        ttl = self.GLOBAL_MUTEX_TTL
        try:
            while True:
                # Use a strictly non-blocking or very short sleep wait for the global lock
                acquired = await self._await_redis(self.cache_client.set(lock_key, token, nx=True, ex=ttl))
                if acquired:
                    return _RedisMutexGuard(self.cache_client, lock_key, token)
                await asyncio.sleep(0.5)
        except Exception:
            return _NullAsyncContext()

    def _log_request_start(self, task: str, user_id: str | None, text: str) -> None:
        logger.info(
            "TS request received task=%s time=%s user=%s instance=%s text=%s",
            task,
            time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            self._safe_log_user(user_id),
            self.instance_id,
            self._safe_log_text(text),
        )

    @staticmethod
    def _safe_log_user(user_id: str | None) -> str:
        value = str(user_id or "anonymous").strip()
        return value[:64] if value else "anonymous"

    @staticmethod
    def _safe_log_text(text: str, limit: int = 180) -> str:
        value = re.sub(r"\s+", " ", str(text or "")).strip()
        return value[:limit]

    @staticmethod
    def _split_into_sections(text: str) -> list[dict[str, str | int]]:
        source = (text or "").strip()
        if not source:
            return [{"title": "Document", "level": 1, "content": ""}]

        # Try to split by markdown-like headers
        headers = list(re.finditer(r"^(#{1,6})\s+(.+)$", source, flags=re.MULTILINE))
        if not headers:
            return [{"title": "Document", "level": 1, "content": source}]

        sections: list[dict[str, str | int]] = []
        for i, match in enumerate(headers):
            level = len(match.group(1))
            title = match.group(2).strip()
            start = match.end()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(source)
            content = source[start:end].strip()
            sections.append({"title": title, "level": level, "content": content})

        return sections

    @staticmethod
    def _estimate_section_summary_words(source_words: int, max_words: int | None) -> int:
        if max_words is None:
            return max(100, source_words // 2)
        return max(40, max_words)

    @staticmethod
    def _render_structured_summary(sections: list[dict[str, str | int]]) -> str:
        lines: list[str] = []
        for section in sections:
            prefix = "#" * int(section.get("level") or 1)
            lines.append(f"{prefix} {section.get('title')}\n\n{section.get('summary')}")
        return "\n\n".join(lines).strip()

    @staticmethod
    def _post_process_summary(text: str) -> str:
        output = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        output = re.sub(r"[ \t]+", " ", output)
        output = re.sub(r"\n{3,}", "\n\n", output)
        return output.strip()

    @staticmethod
    def _rebalance_chunks(chunks: list[str], *, max_chunks: int) -> list[str]:
        cleaned = [chunk.strip() for chunk in chunks if str(chunk or '').strip()]
        if not cleaned:
            return []
        max_chunks = max(1, int(max_chunks))
        if len(cleaned) <= max_chunks:
            return cleaned
        bucket_size = (len(cleaned) + max_chunks - 1) // max_chunks
        merged: list[str] = []
        for index in range(0, len(cleaned), bucket_size):
            merged.append("\n\n".join(cleaned[index:index + bucket_size]).strip())
        return [chunk for chunk in merged if chunk]

    @staticmethod
    def _rebalance_sections(sections: list[dict[str, str | int]], *, max_sections: int) -> list[dict[str, str | int]]:
        cleaned = [section for section in sections if str(section.get("title", "")).strip() or str(section.get("content", "")).strip()]
        if not cleaned:
            return [{"title": "Document", "level": 1, "content": ""}]
        max_sections = max(1, int(max_sections))
        if len(cleaned) <= max_sections:
            return cleaned
        bucket_size = (len(cleaned) + max_sections - 1) // max_sections
        merged_sections: list[dict[str, str | int]] = []
        for index in range(0, len(cleaned), bucket_size):
            bucket = cleaned[index:index + bucket_size]
            title = str(bucket[0].get("title") or "Section").strip() or "Section"
            level = min(int(section.get("level") or 1) for section in bucket)
            content = "\n\n".join(str(section.get("content") or "").strip() for section in bucket if str(section.get("content") or "").strip())
            merged_sections.append({"title": title, "level": level, "content": content})
        return merged_sections

    @classmethod
    def _split_into_chunks(cls, text: str, max_chars: int = DEFAULT_CHUNK_SIZE) -> list[str]:
        return cls.smart_rechunk(text, chunk_size=max_chars, chunk_overlap=cls.DEFAULT_CHUNK_OVERLAP)

    @classmethod
    def smart_rechunk(cls, text: str, *, chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[str]:
        source = str(text or "").strip()
        if not source:
            return [""]
        if len(source) <= chunk_size:
            return [source]
        if RecursiveCharacterTextSplitter is None:
            return cls.simple_rechunk(source, max_chars=chunk_size)
        safe_overlap = max(0, min(int(chunk_overlap), max(0, int(chunk_size) - 1)))
        separators = ["\n\n", "\n", ". ", "! ", "? ", "؟ ", "; ", "، ", " ", ""]
        try:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=int(chunk_size),
                chunk_overlap=safe_overlap,
                length_function=len,
                separators=separators,
                is_separator_regex=False,
            )
            chunks = [c.strip() for c in splitter.split_text(source) if c and c.strip()]
            return chunks or cls.simple_rechunk(source, max_chars=chunk_size)
        except Exception:
            return cls.simple_rechunk(source, max_chars=chunk_size)

    @classmethod
    def simple_rechunk(cls, text: str, max_chars: int = DEFAULT_CHUNK_SIZE) -> list[str]:
        source = str(text or "")
        if len(source) <= max_chars:
            return [source]
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", source) if p.strip()]
        if not paragraphs:
            return [source]
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0
        def flush() -> None:
            nonlocal current, current_len
            if current:
                chunks.append("\n\n".join(current).strip())
                current = []
                current_len = 0
        for paragraph in paragraphs:
            if len(paragraph) > max_chars:
                flush()
                chunks.extend(cls._split_large_paragraph(paragraph, max_chars))
                continue
            projected = current_len + len(paragraph) + (2 if current else 0)
            if projected > max_chars:
                flush()
            current.append(paragraph)
            current_len += len(paragraph) + (2 if len(current) > 1 else 0)
        flush()
        return chunks or [source]

    @staticmethod
    def _split_large_paragraph(paragraph: str, max_chars: int) -> list[str]:
        sentences = [s.strip() for s in re.split(r"(?<=[\.!\?؟])\s+", paragraph) if s.strip()]
        if not sentences:
            return [paragraph[:max_chars]] + ([paragraph[max_chars:]] if len(paragraph) > max_chars else [])
        parts: list[str] = []
        current = ""
        for sentence in sentences:
            candidate = f"{current} {sentence}".strip() if current else sentence
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    parts.append(current)
                if len(sentence) <= max_chars:
                    current = sentence
                else:
                    hard_parts = [sentence[i:i + max_chars] for i in range(0, len(sentence), max_chars)]
                    parts.extend(hard_parts[:-1])
                    current = hard_parts[-1]
        if current:
            parts.append(current)
        return parts

    @staticmethod
    def _post_process_translation(text: str) -> str:
        output = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        output = re.sub(r"[ \t]+", " ", output)
        output = re.sub(r"\n{3,}", "\n\n", output)
        output = re.sub(r"\s+([,.;:!?])", r"\1", output)
        output = re.sub(r"([\(\[\{])\s+", r"\1", output)
        output = re.sub(r"\s+([\)\]\}])", r"\1", output)
        return output.strip()

    @staticmethod
    def _merge_chunks(chunks: list[str]) -> str:
        return "\n\n".join(chunk.strip() for chunk in chunks if chunk and chunk.strip()).strip()


class _RedisMutexGuard:
    def __init__(self, client: Redis, key: str, token: str) -> None:
        self.client = client
        self.key = key
        self.token = token

    async def __aenter__(self) -> _RedisMutexGuard:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            current = await TranslationSummarizationService._await_redis(self.client.get(self.key))
            if current == self.token:
                await TranslationSummarizationService._await_redis(self.client.delete(self.key))
        except Exception:
            pass


class _NullAsyncContext:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass
