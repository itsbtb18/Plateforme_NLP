from __future__ import annotations

import re

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.schemas import ChatRequest, SummarizeRequest, TaskResponse, TranslateRequest
from app.service import TranslationSummarizationService

app = FastAPI(title="Translation & Summarization Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
settings = get_settings()
svc = TranslationSummarizationService()


def _authorize(api_key: str | None) -> None:
    expected = settings.TS_SERVICE_API_KEY.strip()
    if not expected:
        return
    if not api_key or api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid TS service API key")


def _service_error_to_http(exc: Exception) -> None:
    message = str(exc or "").strip() or "Translation/Summarization provider failed"
    lowered = message.lower()

    if "queue" in lowered and "too many" in lowered:
        raise HTTPException(
            status_code=429,
            detail="Too many tasks in queue. Please wait for previous tasks to finish before adding more.",
        )

    if "429" in lowered or "rate limit" in lowered or "too many requests" in lowered:
        retry_after_match = re.search(r"(?:retry after|try again in|waiting)\s*(\d+(?:\.\d+)?)", message, flags=re.IGNORECASE)
        retry_hint = ""
        if retry_after_match:
            retry_seconds = max(1, min(20, int(float(retry_after_match.group(1)))))
            retry_hint = f" Please retry after {retry_seconds}s."
        raise HTTPException(
            status_code=429,
            detail=f"AI provider rate limit reached.{retry_hint} Please wait a moment and retry.",
        )

    if "api key" in lowered or "unauthorized" in lowered or "forbidden" in lowered:
        raise HTTPException(
            status_code=502,
            detail="AI provider authentication failed. Check provider API keys.",
        )

    raise HTTPException(status_code=502, detail=message)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "primary_provider": svc.provider_order()[0],
        "fallback_provider": svc.provider_order()[1],
    }


@app.post("/translate", response_model=TaskResponse)
async def translate(req: TranslateRequest, x_ts_api_key: str | None = Header(default=None)) -> TaskResponse:
    _authorize(x_ts_api_key)
    try:
        output, provider_used, fallback_used = await svc.translate(
            text=req.text,
            source_language=req.source_language,
            target_language=req.target_language,
            user_id=req.user_id,
        )
    except Exception as exc:
        _service_error_to_http(exc)
    return TaskResponse(
        task="translation",
        output=output,
        provider_used=provider_used,
        fallback_used=fallback_used,
    )


@app.post("/summarize", response_model=TaskResponse)
async def summarize(req: SummarizeRequest, x_ts_api_key: str | None = Header(default=None)) -> TaskResponse:
    _authorize(x_ts_api_key)
    try:
        output, provider_used, fallback_used = await svc.summarize(
            text=req.text,
            language=req.language,
            style=req.style,
            max_words=req.max_words,
            user_id=req.user_id,
        )
    except Exception as exc:
        _service_error_to_http(exc)
    return TaskResponse(
        task="summarization",
        output=output,
        provider_used=provider_used,
        fallback_used=fallback_used,
    )


@app.post("/chat", response_model=TaskResponse)
async def chat(req: ChatRequest, x_ts_api_key: str | None = Header(default=None)) -> TaskResponse:
    _authorize(x_ts_api_key)
    try:
        output, provider_used, fallback_used = await svc.chat(
            system_prompt=req.system_prompt,
            user_prompt=req.user_prompt,
            provider_name=req.provider,
            user_id=req.user_id,
        )
    except Exception as exc:
        _service_error_to_http(exc)
    return TaskResponse(
        task="chat",
        output=output,
        provider_used=provider_used,
        fallback_used=fallback_used,
    )
