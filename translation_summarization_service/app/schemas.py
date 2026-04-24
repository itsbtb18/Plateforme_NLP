from pydantic import BaseModel, Field


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1)
    source_language: str = Field(min_length=2)
    target_language: str = Field(min_length=2)
    user_id: str | None = Field(default=None, description="Optional user identifier for queueing and fairness")


class SummarizeRequest(BaseModel):
    text: str = Field(min_length=1)
    language: str = Field(default="en")
    style: str = Field(default="brief")
    max_words: int | None = Field(default=None, ge=20, le=2000)
    user_id: str | None = Field(default=None, description="Optional user identifier for queueing and fairness")


class ChatRequest(BaseModel):
    system_prompt: str = Field(default="You are a helpful assistant.")
    user_prompt: str = Field(min_length=1)
    provider: str | None = Field(default=None, description="Force a specific provider (gemini|groq)")
    user_id: str | None = Field(default=None)


class TaskResponse(BaseModel):
    task: str
    output: str
    provider_used: str
    fallback_used: bool
