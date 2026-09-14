import logging
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from app.api.deps import IdentityDep, RunnerDep, SettingsDep, StoreDep, UseCaseDep
from app.config.loader import UseCaseNotFoundError
from app.schemas.agent import AgentState, UsageSummary
from app.schemas.conversation import (
    Citation,
    Conversation,
    CreateConversationRequest,
    CreateConversationResponse,
    Message,
    MessageRole,
    SendMessageRequest,
)
from app.schemas.events import EventType, complete_event, error_event, status_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["conversations"])


@router.post("/conversations", status_code=201)
async def create_conversation(
    body: CreateConversationRequest,
    user: IdentityDep,
    store: StoreDep,
    loader: UseCaseDep,
    settings: SettingsDep,
) -> CreateConversationResponse:
    usecase_id = body.usecase_id or settings.default_usecase
    try:
        config = loader.get(usecase_id)
    except UseCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    conversation = Conversation(
        user_id=user.employee_id,
        title=body.title or "New conversation",
        usecase_id=config.usecase_id,
        usecase_version=config.version,
    )
    store.create_conversation(conversation)
    logger.info(
        "conversation created",
        extra={"actor": user.employee_id, "action": "conversation_create", "outcome": "ok"},
    )
    return CreateConversationResponse(
        conversation_id=conversation.conversation_id,
        usecase_id=config.usecase_id,
        usecase_version=config.version,
    )


@router.get("/conversations")
async def list_conversations(user: IdentityDep, store: StoreDep) -> list[dict]:
    return [
        {
            "conversation_id": c.conversation_id,
            "title": c.title,
            "usecase_id": c.usecase_id,
            "updated_at": c.updated_at.isoformat(),
        }
        for c in store.list_conversations(user.employee_id)
    ]


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user: IdentityDep,
    store: StoreDep,
) -> Conversation:
    conversation = store.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    if conversation.user_id != user.employee_id:
        raise HTTPException(status_code=403, detail="not authorized for this conversation")
    return conversation


@router.post("/conversations/{conversation_id}/messages:stream")
async def stream_message(
    conversation_id: str,
    body: SendMessageRequest,
    request: Request,
    user: IdentityDep,
    store: StoreDep,
    loader: UseCaseDep,
    runner: RunnerDep,
) -> StreamingResponse:
    conversation = store.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    if conversation.user_id != user.employee_id:
        raise HTTPException(status_code=403, detail="not authorized for this conversation")
    try:
        config = loader.get(conversation.usecase_id)
    except UseCaseNotFoundError as exc:
        raise HTTPException(
            status_code=500, detail="use case config no longer available"
        ) from exc

    async def event_stream():
        correlation_id = request.state.correlation_id
        yield status_event("persist", "saving user message").to_ndjson()
        user_msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=body.content,
            correlation_id=correlation_id,
        )
        store.add_message(user_msg)

        state = AgentState(
            conversation_id=conversation_id,
            user=user,
            usecase_id=config.usecase_id,
            usecase_version=config.version,
            usecase_config=config,
        )
        tokens: list[str] = []
        citations: list[dict] = []
        usage = UsageSummary()
        try:
            async for event in runner.run(state, body.content):
                if event.type == EventType.TOKEN:
                    tokens.append(event.data["text"])
                elif event.type == EventType.USAGE:
                    usage = UsageSummary.model_validate(event.data)
                elif event.type == EventType.CITATION:
                    citations.append(event.data)
                yield event.to_ndjson()
        except Exception:
            logger.exception("agent run failed", extra={"action": "agent_run", "outcome": "error"})
            yield error_event(
                "agent_error", "The assistant hit an unexpected error.", retryable=True
            ).to_ndjson()
            return

        assistant_msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content="".join(tokens).strip(),
            citations=[Citation.model_validate(c) for c in citations],
            usage=usage,
            correlation_id=correlation_id,
        )
        store.add_message(assistant_msg)
        yield complete_event(assistant_msg.message_id, conversation_id).to_ndjson()

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


class UpdateConversationRequest(BaseModel):
    title: str | None = None
    status: str | None = None  # "active" | "archived"


@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    body: UpdateConversationRequest,
    user: IdentityDep,
    store: StoreDep,
) -> dict:
    """FR-04: rename or archive a conversation (owner only)."""
    conversation = store.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    if conversation.user_id != user.employee_id:
        raise HTTPException(status_code=403, detail="not authorized for this conversation")
    if body.title:
        store.update_conversation_title(conversation_id, body.title)
    if body.status in ("active", "archived"):
        store.set_conversation_status(conversation_id, body.status)
    return {"conversation_id": conversation_id, "updated": True}


class FeedbackRequest(BaseModel):
    rating: Literal["up", "down"]
    reason: str | None = None
    comment: str | None = None


@router.post("/messages/{message_id}/feedback", status_code=201)
async def submit_feedback(
    message_id: str,
    body: FeedbackRequest,
    request: Request,
    user: IdentityDep,
    store: StoreDep,
) -> dict:
    """FR-20: thumbs rating + reason + comment linked to message/conversation."""
    message = store.get_message(message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="message not found")
    conversation = store.get_conversation(message.conversation_id)
    if conversation is None or conversation.user_id != user.employee_id:
        raise HTTPException(status_code=403, detail="not authorized for this message")
    feedback = store.add_feedback(
        {
            "feedback_id": uuid4().hex,
            "message_id": message_id,
            "conversation_id": message.conversation_id,
            "user_id": user.employee_id,
            "rating": body.rating,
            "reason": body.reason,
            "comment": body.comment,
            "correlation_id": request.state.correlation_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )
    return {"feedback_id": feedback["feedback_id"], "recorded": True}
