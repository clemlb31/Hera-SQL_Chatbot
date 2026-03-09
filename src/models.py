from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    model: Optional[str] = None  # "mistral-small-latest", "mistral-large-latest", "qwen3.5:latest"


class ChatResponse(BaseModel):
    type: str  # "clarify", "confirm_sql", "results", "error", "warning"
    message: str
    sql: Optional[str] = None
    results: Optional[dict] = None
    reasoning: Optional[str] = None
    thinking: Optional[str] = None
    warnings: Optional[list[str]] = None
    corrections: Optional[list[dict]] = None
    conversation_id: str


class ExecuteRequest(BaseModel):
    conversation_id: str
    sql: str
    model: Optional[str] = None
    force: Optional[bool] = False
