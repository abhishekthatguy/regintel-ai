import asyncio
import time
from collections.abc import AsyncIterator
from typing import Protocol

from app.schemas.agent import AgentState, UsageSummary
from app.schemas.events import StreamEvent, status_event, token_event, usage_event


class AgentRunner(Protocol):
    """Runs the agent for one user message, streaming events.
    Phase 0: stub. Phase 1: LangGraph implementation behind this signature.

    Contract: yields `status`, `token`, `citation` (P2+), `usage` events.
    The API layer assembles the assistant message from streamed tokens and
    emits `complete`/`error` itself after persistence."""

    def run(self, state: AgentState, user_message: str) -> AsyncIterator[StreamEvent]: ...


STUB_REPLY = (
    "I'm RegIntel AI, running the Phase 0 walking skeleton. "
    "The full LangGraph agent — knowledge search, ticket lookup, and ticket "
    "creation — lands in Phase 1. You said: “{msg}”"
)


class StubAgentRunner:
    async def run(self, state: AgentState, user_message: str) -> AsyncIterator[StreamEvent]:
        started = time.perf_counter()
        yield status_event("initialize", "request validated")
        await asyncio.sleep(0)
        yield status_event("generate", "stub response")
        text = STUB_REPLY.format(msg=user_message)
        for word in text.split(" "):
            yield token_event(word + " ")
            await asyncio.sleep(0)
        elapsed = (time.perf_counter() - started) * 1000
        prompt_tokens = len(user_message.split())
        completion_tokens = len(text.split())
        usage = UsageSummary(
            model="stub",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=round(elapsed, 1),
        )
        yield usage_event(usage.model_dump())
