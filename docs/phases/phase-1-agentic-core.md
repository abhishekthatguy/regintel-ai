# Phase 1 — Local Agentic Core (IIT Project 3 Baseline) ★ MANDATORY

**Goal:** the complete IIT Project 3 deliverable — a fully working local agentic assistant. **This phase alone must satisfy every official Project 3 expectation.** Later phases only add enterprise integrations.

## End-to-end slice after this phase

A user opens Streamlit, selects a demo employee + use case, and chats with the assistant. It answers questions from the local knowledge corpus **with citations**, looks up their tickets, creates tickets through a clarify → duplicate-check → confirm → create flow, remembers context across turns, handles refusals and tool failures gracefully, and persists everything to SQLite. An eval page runs the rubric suite.

## Scope

### LangGraph graph (all BRD §9 nodes)
- Full node set: Initialize → Classify/Plan → {Clarify, Build Filters→Retrieve+Rerank, Ticket Lookup, Duplicate Check→Confirm Action→Ticket Create, Direct} → Generate → Guardrail(basic) → Process Response → Persist; Error Handler with bounded retry
- `AgentState`: messages, user context, use case, intent, filters, tool results, citations, pending action, errors
- Conditional routing among direct / search / lookup / create / clarify / refusal / failure paths (FR-06)

### Three tools (behind a `Tool` interface)
1. **Knowledge Search** — local retrieval over sample corpus: keyword (BM25) + optional local embeddings (e.g. sentence-transformers + SQLite/FAISS), merged + threshold-scored. Returns ranked evidence with source metadata. Interface designed so Phase 2 swaps in OpenSearch without touching the node.
2. **Ticket Lookup** — queries `tickets` by employee; returns only the authenticated employee's tickets; never invents missing values.
3. **Ticket Create** — required-field validation (category, description, priority), duplicate check against open tickets, explicit user confirmation, idempotency key, unique ticket + audit record.

### Conversation & memory
- Conversations: create, continue, rename, archive (FR-04)
- Multi-turn context: follow-ups resolve references ("what about contractors?"); pending action survives clarification turns
- Feedback: thumbs up/down + reason + comment linked to message/conversation (FR-20)

### Generation
- One configured LLM provider (env-selected: Bedrock Claude, OpenAI-compatible, or local) behind a `ChatModel` interface
- Grounded prompt: answer only from supplied evidence; emit citation markers; "evidence not found" path offers escalation
- Basic citations: citation_id, title, source ref, excerpt (full contract in P2)

### Guardrails (basic, app-level)
- Prompt-injection heuristics on retrieved text (untrusted-content isolation)
- Off-domain/harmful request refusal path; tool allowlist per use case

### Streamlit UI (FR-27)
- **Chat**: message stream, expandable citations, tool-activity badges, feedback controls, error toasts
- **Admin**: inspect loaded USECASE config, conversations, tickets, usage log
- **Eval**: run rubric suite, view per-dimension scores + traces

### Config
- USECASE config in YAML/SQLite: `usecase_id, system_prompt, tools_enabled, filters, model, thresholds`; second demo use case (e.g., HR alongside IT) to prove configurability
- Stub identity: selectable demo employees with department claim → drives retrieval filters

### Evaluator v1 (FR-26)
- Golden dataset: ~30 cases covering UJ-01..UJ-05 + edge cases
- Deterministic checks: routing, tool selection + args, duplicate prevention (100%), safety blocks, citation resolution
- Judged checks: groundedness/relevance/completeness via configured LLM judge with rubric prompt

## Out of scope this phase

Real Entra ID, cloud stores, OpenSearch, real Graph/OpenText, streaming protocol, Angular, multilingual, voice.

## Exit criteria — official Project 3 demo scenarios all pass locally

- [ ] ≥3 tools execute via conditional routing, visibly in the UI
- [ ] Knowledge answers carry citations or an explicit not-found + escalation
- [ ] Multi-turn ticket flow retains employee ID, issue details, pending action
- [ ] Ticket creation blocked without required fields/confirmation; duplicates reuse existing ticket (100% in eval)
- [ ] Tool failure → graceful actionable error, no invented data
- [ ] Rubric report: routing/tool ≥90%, safety 100%, judged dims ≥4/5 avg
- [ ] README: setup + run + demo script; tests green in CI; no secrets

## Key risks

- Local retrieval quality on tiny corpus → keep corpus small/clean, tune threshold, don't over-claim relevance numbers
- LLM classification flakiness → constrained tool schemas + retry with corrective prompt; deterministic fallback for demo-critical paths
