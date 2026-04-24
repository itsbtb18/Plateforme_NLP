from pydantic import BaseModel, Field


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1)
    source_language: str = Field(min_length=2)
    target_language: str = Field(min_length=2)


class SummarizeRequest(BaseModel):
    text: str = Field(min_length=1)
    language: str = Field(default="en")
    style: str = Field(default="brief")
    max_words: int | None = Field(default=None, ge=20, le=2000)


class TaskResponse(BaseModel):
    task: str
    output: str
    provider_used: str
    fallback_used: bool
