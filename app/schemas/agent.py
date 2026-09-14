from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.identity import UserContext


class ToolStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


class ToolResult(BaseModel):
    tool_name: str
    call_id: str
    status: ToolStatus
    output: Any = None
    error: str | None = None
    latency_ms: float | None = None


class UsageSummary(BaseModel):
    model: str = "stub"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: float = 0.0


class PendingAction(BaseModel):
    """An action awaiting clarification or confirmation across turns (FR-05)."""

    action_type: str
    collected_fields: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    awaiting_confirmation: bool = False


class AgentState(BaseModel):
    """LangGraph conversation state (FR-05). Phase 0 carries the subset the
    stub runner needs; Phase 1 persists it via checkpointer."""

    conversation_id: str
    user: UserContext
    usecase_id: str
    usecase_version: int = 1
    intent: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    tool_results: list[ToolResult] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)
    pending_action: PendingAction | None = None
    errors: list[str] = Field(default_factory=list)
