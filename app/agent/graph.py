"""LangGraph agent — Phase 1 implementation of the BRD §9 node spec.

Topology:
  initialize -> classify -> {direct->generate, knowledge->build_filters->retrieve->generate,
    ticket_lookup, ticket_create->(clarify|duplicate_check->(confirm_action|respond)),
    confirm->ticket_create, cancel/reconfirm->respond}
  all paths -> guardrail -> respond -> END
  node failures -> error_handler -> guardrail

Multi-turn state (pending_action, history, last_topic) persists via SqliteSaver
keyed on thread_id = conversation_id.
"""

import dataclasses
import logging
import time
from typing import Any, TypedDict

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from app.guardrails.checks import check_input, check_output
from app.llm.base import (
    INTENT_CANCEL,
    INTENT_CONFIRM,
    INTENT_CRM_CASE_CREATE,
    INTENT_CRM_LOOKUP,
    INTENT_DIRECT,
    INTENT_KNOWLEDGE,
    INTENT_TICKET_CREATE,
    INTENT_TICKET_LOOKUP,
    is_cancellation,
    is_confirmation,
)
from app.schemas.config import UseCaseConfig
from app.schemas.conversation import Citation
from app.tools.base import ToolContext
from app.tools.knowledge import KnowledgeSearchTool
from app.tools.tickets import TicketCreateTool, TicketLookupTool, validate_fields

logger = logging.getLogger(__name__)


class GraphState(TypedDict, total=False):
    user_message: str
    user: dict[str, Any]
    usecase: dict[str, Any]
    history: list[dict[str, str]]
    intent: str
    fields: dict[str, Any]
    missing: list[str]
    duplicate: bool
    filters: dict[str, Any]
    pending_action: dict[str, Any] | None
    offered_action: dict[str, Any] | None
    evidence: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    language: str
    answer: str
    usage: dict[str, Any]
    error: str | None
    last_topic: str


def build_graph(ctx: ToolContext, model, checkpointer) -> Any:
    """Compile the agent graph. ctx supplies tools/stores/index; model is the
    ChatModel implementation; checkpointer provides multi-turn memory."""

    knowledge_tool = KnowledgeSearchTool()
    lookup_tool = TicketLookupTool()
    create_tool = TicketCreateTool()
    from app.tools.crm import CRMCaseCreateTool, CRMLookupTool, validate_case_fields

    crm_tool = CRMLookupTool()
    crm_create_tool = CRMCaseCreateTool()

    def req_ctx(state: GraphState) -> ToolContext:
        """Request-scoped tool context: shared stores/index + this turn's user.
        ctx itself is built once per use case and must never carry user data."""
        from app.schemas.identity import UserContext

        return dataclasses.replace(ctx, user=UserContext.model_validate(state["user"]))

    def node(name):
        def deco(fn):
            def wrapped(state: GraphState) -> dict:
                logger.info("node", extra={"action": "node", "outcome": name})
                return fn(state)

            return wrapped

        return deco

    @node("initialize")
    def initialize(state: GraphState) -> dict:
        result = check_input(state["user_message"])
        if not result.allowed:
            return {
                "answer": model.respond("refusal"),
                "error": f"input_blocked:{result.reason}",
                "history": state.get("history", []),
            }
        return {"error": None, "history": state.get("history", [])}

    INTENT_TOOL = {
        INTENT_KNOWLEDGE: "knowledge_search",
        INTENT_TICKET_LOOKUP: "ticket_lookup",
        INTENT_TICKET_CREATE: "ticket_create",
        INTENT_CRM_LOOKUP: "crm_lookup",
        INTENT_CRM_CASE_CREATE: "crm_case_create",
    }

    def _mine_missing_fields(fields: dict, history: list, extractor, validator) -> dict:
        """Multi-turn memory: fill still-missing fields from earlier user
        turns — information already given in the conversation counts.
        Only knowledge-classified turns are mined (user statements/questions),
        never commands, confirms, or cancels."""
        recent = [m["content"].strip() for m in history if m.get("role") == "user"]
        for text in reversed(recent[-6:]):
            _, missing = validator(fields)
            if not missing:
                break
            if len(text) < 10 or is_confirmation(text) or is_cancellation(text):
                continue
            if model.classify(text, {"pending_action": None, "history": []}) != INTENT_KNOWLEDGE:
                continue
            candidate = extractor(text, {})
            for key in missing:
                if key in candidate:
                    fields[key] = candidate[key]
        return fields

    @node("classify")
    def classify(state: GraphState) -> dict:
        context = {"pending_action": state.get("pending_action"), "history": state.get("history", [])}
        message = state["user_message"]
        intent = model.classify(message, context)

        # Offered-action memory: a knowledge answer that ended with
        # "let me know if you'd like me to create a ticket" sets
        # offered_action; a bare "yes"/"no" reply acts on that offer.
        offered = state.get("offered_action")
        if offered and intent not in (INTENT_CONFIRM, INTENT_CANCEL):
            if is_confirmation(message):
                intent = offered.get("action_type") or INTENT_TICKET_CREATE
            elif is_cancellation(message):
                return {
                    "intent": INTENT_DIRECT,
                    "answer": model.respond("offer_declined"),
                    "offered_action": None,
                }

        # Tool allowlist is enforced server-side from use-case config —
        # a disabled tool can never execute regardless of the request.
        required_tool = INTENT_TOOL.get(intent)
        if required_tool and required_tool not in ctx.usecase.enabled_tools():
            available = ", ".join(ctx.usecase.enabled_tools()) or "nothing yet"
            return {
                "intent": INTENT_DIRECT,
                "answer": model.respond("tool_disabled", available=available),
                "offered_action": None,
            }

        update: dict = {"intent": intent, "offered_action": None}

        if intent == INTENT_CANCEL and state.get("pending_action"):
            update["pending_action"] = None
            update["answer"] = model.respond("cancelled")
        elif intent == INTENT_TICKET_CREATE:
            fields = model.extract_fields(message, state.get("fields", {}))
            fields = _mine_missing_fields(
                fields, state.get("history", []), model.extract_fields, validate_fields
            )
            clean, missing = validate_fields(fields)
            update["fields"] = clean
            update["missing"] = missing
            update["pending_action"] = {
                "action_type": "ticket_create",
                "collected_fields": clean,
                "missing_fields": missing,
                "awaiting_confirmation": False,
            }
        elif intent == INTENT_CRM_CASE_CREATE:
            fields = model.extract_case_fields(message, state.get("fields", {}))
            fields = _mine_missing_fields(
                fields, state.get("history", []), model.extract_case_fields, validate_case_fields
            )
            clean, missing = validate_case_fields(fields)
            update["fields"] = clean
            update["missing"] = missing
            update["pending_action"] = {
                "action_type": "crm_case_create",
                "collected_fields": clean,
                "missing_fields": missing,
                "awaiting_confirmation": False,
            }
        return update

    @node("clarify")
    def clarify(state: GraphState) -> dict:
        pending = state.get("pending_action") or {}
        missing = state.get("missing") or pending["missing_fields"]
        template = "clarify_case" if pending.get("action_type") == "crm_case_create" else "clarify"
        return {"answer": model.respond(template, missing=", ".join(missing))}

    @node("build_filters")
    def build_filters(state: GraphState) -> dict:
        department = ctx.usecase.filters.department
        return {"filters": {"department": department, "acl_enforced": True}}

    @node("retrieve")
    def retrieve(state: GraphState) -> dict:
        try:
            from app.retrieval.rewriter import get_rewriter

            query = get_rewriter(ctx.usecase.models.enrichment).rewrite(
                state["user_message"],
                {"last_topic": state.get("last_topic"), "history": state.get("history", [])},
            )
            result = knowledge_tool.run(req_ctx(state), query)
            if not result["found"]:
                from app.audit import record_audit

                rctx = req_ctx(state)
                record_audit(
                    rctx.store,
                    actor=rctx.user.employee_id,
                    action="knowledge_not_found",
                    outcome="no_evidence",
                    detail={"query": query[:200], "usecase": ctx.usecase.usecase_id},
                )
                return {
                    "answer": model.respond("not_found"),
                    "evidence": [],
                    "citations": [],
                    "offered_action": {"action_type": "ticket_create"},
                }
            return {
                "evidence": result["evidence"],
                "citations": [c.model_dump(mode="json") for c in result["citations"]],
                "last_topic": result["evidence"][0]["chunk"]["title"],
            }
        except Exception as exc:
            return {"error": f"knowledge_search:{exc}"}

    @node("ticket_lookup")
    def ticket_lookup(state: GraphState) -> dict:
        try:
            result = lookup_tool.run(req_ctx(state))
            if not result["found"]:
                return {"answer": model.respond("ticket_none", scope="")}
            lines = ["Here are your tickets:\n"]
            for t in result["tickets"]:
                lines.append(
                    f"- **{t['ticket_id']}** · {t['category']} · {t['status']} · "
                    f"{t['priority']} — {t['description']}"
                )
            return {"answer": model.respond("ticket_list", lines="\n".join(lines))}
        except Exception as exc:
            return {"error": f"ticket_lookup:{exc}"}

    @node("crm_lookup")
    def crm_lookup(state: GraphState) -> dict:
        try:
            rctx = req_ctx(state)
            result = crm_tool.run(rctx, state["user_message"])
            from app.audit import record_audit

            record_audit(
                rctx.store,
                actor=rctx.user.employee_id,
                action="crm_lookup",
                outcome="ok" if result["found"] else "not_found",
                detail={"usecase": rctx.usecase.usecase_id},
            )
            if not result["found"]:
                return {"answer": model.respond("crm_none")}
            lines = ["Here are your CRM cases:\n"]
            for c in result["cases"]:
                lines.append(
                    f"- **{c['case_id']}** · {c['status']} · {c['priority']} — "
                    f"{c['subject']} ({c['account']})"
                )
            return {"answer": model.respond("ticket_list", lines="\n".join(lines))}
        except Exception as exc:
            return {"error": f"crm_lookup:{exc}"}

    @node("duplicate_check")
    def duplicate_check(state: GraphState) -> dict:
        try:
            pending = state["pending_action"]
            fields = pending["collected_fields"]
            rctx = req_ctx(state)
            if pending.get("action_type") == "crm_case_create":
                dup = rctx.crm.find_duplicate_case(rctx.user.employee_id, fields["subject"])
                if dup:
                    return {
                        "answer": model.respond(
                            "case_duplicate",
                            case_id=dup["case_id"],
                            status=dup["status"],
                            priority=dup["priority"],
                            subject=dup["subject"],
                        ),
                        "pending_action": None,
                        "fields": {},
                        "duplicate": True,
                    }
                return {"duplicate": False}
            dup = rctx.store.find_duplicate_ticket(
                rctx.user.employee_id, fields["category"]
            )
            if dup:
                return {
                    "answer": model.respond(
                        "duplicate",
                        ticket_id=dup["ticket_id"],
                        category=dup["category"],
                        status=dup["status"],
                        priority=dup["priority"],
                        description=dup["description"],
                    ),
                    "pending_action": None,
                    "fields": {},
                    "duplicate": True,
                }
            return {"duplicate": False}
        except Exception as exc:
            return {"error": f"duplicate_check:{exc}"}

    @node("confirm_action")
    def confirm_action(state: GraphState) -> dict:
        pending = dict(state["pending_action"])
        pending["awaiting_confirmation"] = True
        fields = pending["collected_fields"]
        if pending.get("action_type") == "crm_case_create":
            answer = model.respond(
                "confirm_case",
                subject=fields["subject"],
                priority=fields.get("priority", "medium"),
                description=fields["description"],
            )
        else:
            answer = model.respond(
                "confirm",
                category=fields["category"],
                priority=fields.get("priority", "medium"),
                description=fields["description"],
            )
        return {"pending_action": pending, "answer": answer}

    @node("ticket_create")
    def ticket_create(state: GraphState) -> dict:
        try:
            pending = state.get("pending_action") or {}
            fields, missing = validate_fields(pending.get("collected_fields", {}))
            if missing:
                return {
                    "answer": model.respond("clarify", missing=", ".join(missing)),
                    "pending_action": {**pending, "missing_fields": missing, "awaiting_confirmation": False},
                }
            rctx = req_ctx(state)
            dup = rctx.store.find_duplicate_ticket(rctx.user.employee_id, fields["category"])
            if dup:
                return {
                    "answer": model.respond(
                        "duplicate",
                        ticket_id=dup["ticket_id"],
                        category=dup["category"],
                        status=dup["status"],
                        priority=dup["priority"],
                        description=dup["description"],
                    ),
                    "pending_action": None,
                    "fields": {},
                }
            idem = f"{rctx.user.employee_id}:{fields['category']}:{fields['description'][:40]}"
            result = create_tool.run(rctx, fields, idempotency_key=idem)
            ticket = result["ticket"]
            from app.audit import record_audit

            record_audit(
                rctx.store,
                actor=rctx.user.employee_id,
                action="ticket_create",
                outcome=ticket["ticket_id"],
                detail={
                    "category": ticket["category"],
                    "priority": ticket["priority"],
                    "usecase": ctx.usecase.usecase_id,
                    "model": ctx.usecase.models.generation,
                },
            )
            return {
                "answer": model.respond(
                    "created",
                    ticket_id=ticket["ticket_id"],
                    category=ticket["category"],
                    priority=ticket["priority"],
                ),
                "pending_action": None,
                "fields": {},
            }
        except Exception as exc:
            return {"error": f"ticket_create:{exc}"}

    @node("crm_case_create")
    def crm_case_create(state: GraphState) -> dict:
        try:
            pending = state.get("pending_action") or {}
            fields, missing = validate_case_fields(pending.get("collected_fields", {}))
            if missing:
                return {
                    "answer": model.respond("clarify_case", missing=", ".join(missing)),
                    "pending_action": {**pending, "missing_fields": missing, "awaiting_confirmation": False},
                }
            rctx = req_ctx(state)
            idem = f"{rctx.user.employee_id}:{fields['subject'][:40]}"
            result = crm_create_tool.run(rctx, fields, idempotency_key=idem)
            case = result["case"]
            if not result["created"]:
                return {
                    "answer": model.respond(
                        "case_duplicate",
                        case_id=case["case_id"],
                        status=case["status"],
                        priority=case["priority"],
                        subject=case["subject"],
                    ),
                    "pending_action": None,
                    "fields": {},
                }
            from app.audit import record_audit

            record_audit(
                rctx.store,
                actor=rctx.user.employee_id,
                action="crm_case_create",
                outcome=case["case_id"],
                detail={
                    "priority": case["priority"],
                    "usecase": ctx.usecase.usecase_id,
                    "idempotency_key": idem,
                },
            )
            return {
                "answer": model.respond(
                    "case_created",
                    case_id=case["case_id"],
                    priority=case["priority"],
                ),
                "pending_action": None,
                "fields": {},
            }
        except Exception as exc:
            return {"error": f"crm_case_create:{exc}"}

    @node("generate")
    def generate(state: GraphState) -> dict:
        if state.get("answer"):
            return {}  # not_found/tool_disabled etc. already composed upstream
        if state.get("intent") == INTENT_DIRECT:
            return {"answer": model.respond("greeting", name=state["user"]["name"].split()[0])}
        return {
            "answer": model.generate_grounded(
                state.get("evidence", []), language=state.get("language", "en")
            ),
            "offered_action": {"action_type": "ticket_create"},
        }

    @node("guardrail")
    def guardrail(state: GraphState) -> dict:
        result = check_output(state.get("answer", ""))
        if not result.allowed:
            return {"answer": model.respond("refusal"), "error": f"output_blocked:{result.reason}"}
        return {}

    @node("error_handler")
    def error_handler(state: GraphState) -> dict:
        tool = (state.get("error") or "tool").split(":")[0]
        if state.get("error", "").startswith(("input_blocked", "output_blocked")):
            return {}  # refusal answer already set
        return {"answer": model.respond("tool_error", tool=tool)}

    @node("respond")
    def respond(state: GraphState) -> dict:
        history = state.get("history", []) + [
            {"role": "user", "content": state["user_message"]},
            {"role": "assistant", "content": state.get("answer", "")},
        ]
        from app.llm.pricing import estimate_cost

        usage = {
            "model": ctx.usecase.models.generation,
            "prompt_tokens": len(state["user_message"].split()) + 20 * len(history),
            "completion_tokens": len(state.get("answer", "").split()),
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "latency_ms": 0.0,
            "language": state.get("language", "en"),
        }
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
        usage["estimated_cost_usd"] = estimate_cost(
            getattr(model, "model_id", ""), usage["prompt_tokens"], usage["completion_tokens"]
        )
        return {"history": history[-40:], "usage": usage}

    # --- routing -----------------------------------------------------------

    def route_initialize(state: GraphState) -> str:
        return "guardrail" if (state.get("error") or "").startswith("input_blocked") else "classify"

    def route_classify(state: GraphState) -> str:
        intent = state.get("intent")
        if intent == INTENT_DIRECT:
            return "generate"
        if intent == INTENT_KNOWLEDGE:
            return "build_filters"
        if intent == INTENT_TICKET_LOOKUP:
            return "ticket_lookup"
        if intent == INTENT_CRM_LOOKUP:
            return "crm_lookup"
        if intent == INTENT_CONFIRM:
            action_type = (state.get("pending_action") or {}).get("action_type")
            return "crm_case_create" if action_type == "crm_case_create" else "ticket_create"
        if intent in (INTENT_CANCEL, "reconfirm"):
            if intent == "reconfirm" and state.get("pending_action"):
                return "confirm_action"
            return "guardrail"  # cancelled: answer already set
        if intent in (INTENT_TICKET_CREATE, INTENT_CRM_CASE_CREATE):
            return "clarify" if state.get("missing") else "duplicate_check"
        return "generate"

    def route_classify_error(state: GraphState) -> str:
        return "error_handler" if state.get("error") else route_classify(state)

    def route_after_tool(state: GraphState, next_node: str) -> str:
        return "error_handler" if state.get("error") else next_node

    def route_duplicate(state: GraphState) -> str:
        if state.get("error"):
            return "error_handler"
        return "guardrail" if state.get("duplicate") else "confirm_action"

    builder = StateGraph(GraphState)
    for name, fn in [
        ("initialize", initialize),
        ("classify", classify),
        ("clarify", clarify),
        ("build_filters", build_filters),
        ("retrieve", retrieve),
        ("ticket_lookup", ticket_lookup),
        ("crm_lookup", crm_lookup),
        ("duplicate_check", duplicate_check),
        ("confirm_action", confirm_action),
        ("ticket_create", ticket_create),
        ("crm_case_create", crm_case_create),
        ("generate", generate),
        ("guardrail", guardrail),
        ("error_handler", error_handler),
        ("respond", respond),
    ]:
        builder.add_node(name, fn)

    builder.add_edge(START, "initialize")
    builder.add_conditional_edges("initialize", route_initialize)
    builder.add_conditional_edges("classify", route_classify_error)
    builder.add_edge("clarify", "guardrail")
    builder.add_edge("build_filters", "retrieve")
    builder.add_conditional_edges("retrieve", lambda s: route_after_tool(s, "generate"))
    builder.add_conditional_edges("ticket_lookup", lambda s: route_after_tool(s, "guardrail"))
    builder.add_conditional_edges("crm_lookup", lambda s: route_after_tool(s, "guardrail"))
    builder.add_conditional_edges("duplicate_check", route_duplicate)
    builder.add_edge("confirm_action", "guardrail")
    builder.add_conditional_edges("ticket_create", lambda s: route_after_tool(s, "guardrail"))
    builder.add_conditional_edges("crm_case_create", lambda s: route_after_tool(s, "guardrail"))
    builder.add_edge("generate", "guardrail")
    builder.add_edge("error_handler", "guardrail")
    builder.add_edge("guardrail", "respond")
    builder.add_edge("respond", END)

    return builder.compile(checkpointer=checkpointer)


class LangGraphRunner:
    """AgentRunner implementation driving the compiled graph per request.
    The AsyncSqliteSaver checkpointer is created lazily on first run so the
    runner can be built in sync dependency-injection code."""

    class _ConnHandle:
        """Stand-in for the from_conn_string async-context handle that
        teardown code closes via __aexit__."""

        def __init__(self, conn):
            self._conn = conn

        async def __aexit__(self, *_):
            await self._conn.close()

    def __init__(self, ctx_factory, model, checkpoint_db_path: str):
        self._ctx_factory = ctx_factory  # (usecase) -> ToolContext
        self._model = model
        self._db_path = checkpoint_db_path
        self._saver_ctx = None
        self._saver = None
        self._graphs: dict[str, Any] = {}

    async def _graph_for(self, usecase: UseCaseConfig):
        if self._saver is None:
            import aiosqlite

            # Concurrent streams share one SQLite file — a 30s busy timeout
            # turns write-lock contention into a wait instead of a 500.
            conn = await aiosqlite.connect(self._db_path, timeout=30)
            await conn.execute("PRAGMA busy_timeout = 30000")
            await conn.execute("PRAGMA journal_mode = WAL")
            self._saver_ctx = self._ConnHandle(conn)
            self._saver = AsyncSqliteSaver(conn)
        if usecase.usecase_id not in self._graphs:
            self._graphs[usecase.usecase_id] = build_graph(
                self._ctx_factory(usecase), self._model, self._saver
            )
        return self._graphs[usecase.usecase_id]

    async def run(self, state, user_message: str, language: str = "en"):
        from app.schemas.events import status_event, token_event, usage_event

        started = time.perf_counter()
        usecase = state.usecase_config
        graph = await self._graph_for(usecase)
        config = {"configurable": {"thread_id": state.conversation_id}}

        initial: GraphState = {
            "user_message": user_message,
            "user": state.user.model_dump(mode="json"),
            "usecase": usecase.model_dump(mode="json"),
            # Reset per-turn keys; pending_action/fields/history/last_topic are
            # intentionally omitted so the checkpointer carries them forward.
            "intent": "",
            "answer": "",
            "error": None,
            "evidence": [],
            "citations": [],
            "duplicate": False,
            "language": language,
        }

        async for update in graph.astream(initial, config, stream_mode="updates"):
            for node_name in update:
                yield status_event("node", node_name)

        final = await graph.aget_state(config)
        answer = final.values.get("answer", "")

        for chunk in _chunk_text(answer):
            yield token_event(chunk)
        for raw in final.values.get("citations", []):
            yield _citation_event(Citation.model_validate(raw))

        usage = final.values.get("usage", {})
        usage["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        yield usage_event(usage)


def _chunk_text(text: str, size: int = 24):
    for i in range(0, len(text), size):
        yield text[i : i + size]


def _citation_event(citation: Citation):
    from app.schemas.events import EventType, StreamEvent

    return StreamEvent(type=EventType.CITATION, data=citation.model_dump(mode="json"))
