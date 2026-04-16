from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.schemas import SummarizeRequest, TaskResponse, TranslateRequest
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
    output, provider_used, fallback_used = await svc.translate(
        text=req.text,
        source_language=req.source_language,
        target_language=req.target_language,
    )
    return TaskResponse(
        task="translation",
        output=output,
        provider_used=provider_used,
        fallback_used=fallback_used,
    )


@app.post("/summarize", response_model=TaskResponse)
async def summarize(req: SummarizeRequest, x_ts_api_key: str | None = Header(default=None)) -> TaskResponse:
    _authorize(x_ts_api_key)
    output, provider_used, fallback_used = await svc.summarize(
        text=req.text,
        language=req.language,
        style=req.style,
        max_words=req.max_words,
    )
    return TaskResponse(
        task="summarization",
        output=output,
        provider_used=provider_used,
        fallback_used=fallback_used,
    )
