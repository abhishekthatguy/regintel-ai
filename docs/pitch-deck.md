# RegIntel AI — Pitch Deck (source)

Readable source for `docs/submission/RegIntel-AI-Pitch-Deck.pptx`.
Regenerate the deck after edits: `.venv/bin/python scripts/build_pitch_deck.py`.

---

## 1. Title

**RegIntel AI** — Enterprise Knowledge & Operations Assistant
IIT Patna GenAI Development Program · Final Evaluation · Project 3 (Agentic AI)

## 2. The problem

- Fragmented knowledge — policies/SOPs scattered; employees can't find answers.
- Slow, inconsistent support — ticket queues grow while answers already exist.
- Unsupported chatbot answers — no evidence, no citations, no trust.
- Weak auditability & access control — who saw what is untracked.
- Uncontrolled model cost — no token/latency/spend visibility per department.

## 3. The solution

- One agentic assistant: ask → grounded answer with citations → or a governed action.
- LangGraph-orchestrated: 13-node graph, conditional routing, multi-turn state.
- Configuration-driven: departments, tools, guardrails, models in YAML — Finance onboarded with zero new code.
- Enterprise-ready seams: auth, CRM, search, LLM, speech are adapter interfaces.

## 4. Architecture

Employee (Angular / Streamlit / Genesys) → FastAPI (identity, audit, config)
→ LangGraph runner (initialize → classify → conditional route) → tools
(server-side allowlist) → hybrid retriever (BM25 + vector → RRF → rerank,
ACL-filtered) → SQLite store / ingestion / audit / analytics.
Every node emits a status event — the UI shows the live node trace.

## 5. LangGraph workflow

classify routes on intent: knowledge_query → build_filters → retrieve →
generate → guardrail → respond; ticket/crm lookups → tool → respond;
creates → clarify → duplicate_check → confirm_action → write;
confirm/cancel resolves pending actions; error_handler catches tool failures.
Pending actions persist in the SQLite checkpointer across turns.

## 6. Five tools

| Tool | Purpose | Safety |
|---|---|---|
| knowledge_search | Hybrid retrieval over approved corpus | ACL filter + rerank threshold → honest not-found |
| ticket_lookup | Own support tickets | Owner-scoped server-side |
| ticket_create | Validated ticket | Validate → dedupe → confirm → idempotent → audit |
| crm_lookup | CRM case status | Owner-scoped, audited |
| crm_case_create | CRM case | Same full safety contract |

Server-side allowlist per use case — disabled tools can't be invoked.

## 7. Grounded answers — advanced RAG

- Hybrid retrieval: BM25 + vector cosine → reciprocal-rank fusion, both legs ACL-filtered.
- Reranking rescores; weak evidence → not-found, never a guess.
- FR-16 rewriting: follow-ups expanded with conversation context.
- Full citation contract: doc, section, chunk, excerpt, both scores, version, source URL, access decision.
- Ingestion: contextual chunking, checksum drift detection, dead-letter table.

## 8. Safety by design

- Prompt-injection guardrails in/out; Bedrock guardrails merge when configured.
- No blind actions: validate → dedupe → explicit confirm before every write.
- Idempotent writes; department ACLs on both retrieval legs.
- Owner-scoped conversations & exports; full audit trail.

## 9. Beyond the baseline

- 3 departments by config only (IT, HR, Finance).
- Voice: Web Speech mic → same pipeline; read-aloud; SpeechProvider boundary.
- Genesys agent-assist endpoint: stateless grounded suggestions.
- Analytics: usage, feedback, not-found clustering, funnel, dept cost attribution.
- Self-service upload; conversation export (markdown/JSON).

## 10. Quality evidence

- 103 automated tests (unit + integration + security).
- 31-case golden eval suite — runs in pytest AND the Eval page; rubric dims.
- P95 first-token ≈ 65 ms, answer ≈ 70 ms locally (targets 4 s / 12 s).
- CI: ruff + pytest + Angular build on every push.
- docs/requirements-traceability.md maps every requirement to code + tests.

## 11. Demo — five flows

1. "how do I connect to the VPN" → grounded answer + citations
2. "what is the cafeteria menu" → honest not-found
3. "show my tickets" → employee-scoped tool call
4. "create a ticket — laptop battery drains in an hour" → yes → confirm → write → audit
5. "check my case CASE-7001" → CRM lookup (e002 → not-found)

Full walkthrough: docs/demo-script.md

## 12. Technology stack

- LangGraph · tool/context objects · SQLite checkpointer
- Python · FastAPI · Pydantic · NDJSON streaming · Mangum
- BM25 + hashing-vector hybrid → RRF → reranker
- Angular 21 (signals, Tailwind) · Streamlit · Web Speech
- Config-swapped: Entra JWT/JWKS, Bedrock, DynamoDB, Redis, Genesys, OpenText

## 13. Honest limitations

- Local model is deterministic — extractive answers; Bedrock generates fluent prose.
- Enterprise integrations are credential-gated boundaries (fail closed / degrade locally).
- Rubric scores are heuristic proxies until an LLM judge is configured.
- Voice needs a supporting browser (Chrome/Edge).

## 14. Closing

**RegIntel AI** — Understand → Design → Implement → Test → Explain.
Repo README · docs/demo-script.md · docs/requirements-traceability.md ·
pytest: 103 green.
