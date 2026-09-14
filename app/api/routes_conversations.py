import logging

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import StreamingResponse

from app.api.deps import IdentityDep, RunnerDep, SettingsDep, StoreDep, UseCaseDep
from app.config.loader import UseCaseNotFoundError
from app.schemas.agent import AgentState, UsageSummary
from app.schemas.conversation import (
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
        )
        tokens: list[str] = []
        usage = UsageSummary()
        try:
            async for event in runner.run(state, body.content):
                if event.type == EventType.TOKEN:
                    tokens.append(event.data["text"])
                elif event.type == EventType.USAGE:
                    usage = UsageSummary.model_validate(event.data)
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
            usage=usage,
            correlation_id=correlation_id,
        )
        store.add_message(assistant_msg)
        yield complete_event(assistant_msg.message_id, conversation_id).to_ndjson()

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
