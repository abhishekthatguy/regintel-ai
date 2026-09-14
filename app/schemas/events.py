from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EventType(StrEnum):
    STATUS = "status"
    TOKEN = "token"
    CITATION = "citation"
    USAGE = "usage"
    COMPLETE = "complete"
    ERROR = "error"


class StreamEvent(BaseModel):
    """One NDJSON line in the messages:stream response (FR-19 contract)."""

    type: EventType
    data: dict[str, Any] = Field(default_factory=dict)

    def to_ndjson(self) -> str:
        return self.model_dump_json() + "\n"


def status_event(stage: str, detail: str = "") -> StreamEvent:
    return StreamEvent(type=EventType.STATUS, data={"stage": stage, "detail": detail})


def token_event(text: str) -> StreamEvent:
    return StreamEvent(type=EventType.TOKEN, data={"text": text})


def usage_event(usage: dict[str, Any]) -> StreamEvent:
    return StreamEvent(type=EventType.USAGE, data=usage)


def complete_event(message_id: str, conversation_id: str) -> StreamEvent:
    return StreamEvent(
        type=EventType.COMPLETE,
        data={"message_id": message_id, "conversation_id": conversation_id},
    )


def error_event(code: str, message: str, retryable: bool = False) -> StreamEvent:
    return StreamEvent(
        type=EventType.ERROR,
        data={"code": code, "message": message, "retryable": retryable},
    )
