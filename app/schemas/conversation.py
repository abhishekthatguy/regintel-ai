from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid4().hex


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class Citation(BaseModel):
    """Full citation contract per BRD §10.1. Fields are optional in Phase 0;
    retrieval-phase fields are populated from Phase 2."""

    citation_id: str
    document_id: str
    title: str
    source_system: str
    source_ref: str | None = None
    page_section: str | None = None
    chunk_id: str | None = None
    excerpt: str | None = None
    retrieval_score: float | None = None
    rerank_score: float | None = None
    document_version: str | None = None
    access_granted: bool = True


class Message(BaseModel):
    message_id: str = Field(default_factory=_new_id)
    conversation_id: str
    role: MessageRole
    content: str
    citations: list[Citation] = Field(default_factory=list)
    usage: "UsageSummary | None" = None
    correlation_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class Conversation(BaseModel):
    conversation_id: str = Field(default_factory=_new_id)
    user_id: str
    title: str = "New conversation"
    usecase_id: str
    usecase_version: int = 1
    status: ConversationStatus = ConversationStatus.ACTIVE
    messages: list[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class CreateConversationRequest(BaseModel):
    usecase_id: str | None = None
    title: str | None = None


class CreateConversationResponse(BaseModel):
    conversation_id: str
    usecase_id: str
    usecase_version: int


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    language: str = "en"  # FR-22: response language; citations stay original-language


# Late import avoidance: UsageSummary lives in agent.py
from app.schemas.agent import UsageSummary  # noqa: E402

Message.model_rebuild()
