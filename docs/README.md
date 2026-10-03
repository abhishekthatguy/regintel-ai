# RegIntel AI — Project Knowledge Base

Enterprise Knowledge & Operations Assistant — IIT Patna GenAI Development Program, Project 3.

Source of truth for requirements: `../RegIntel_AI_Business_Requirements_Document.docx` (BRD v1.0, baseline for POC).

## Contents

| Doc | Purpose |
|---|---|
| [project-overview.md](project-overview.md) | What RegIntel AI is, business need, success measures, stakeholders, user journeys, scope |
| [architecture.md](architecture.md) | Component map, request data flow, LangGraph agent spec, data model, API surface, security model |
| [decisions-and-open-questions.md](decisions-and-open-questions.md) | Resolved clarifications (OpenText, Genesys Cloud, rubrics) and remaining open questions |
| [evaluation-framework.md](evaluation-framework.md) | Rubric definitions, pass targets, golden dataset approach, CI gates |
| [requirements-traceability.md](requirements-traceability.md) | Every BRD FR/NFR mapped to a delivery phase |
| [diagrams/agent-graph.mmd](diagrams/agent-graph.mmd) | LangGraph node flow — intents, confirm gate, dedupe, guardrail (mirrors `app/agent/graph.py`) |
| [diagrams/system-architecture.mmd](diagrams/system-architecture.mmd) | System flow — clients → API → agent → tools → adapter boundaries (stores/cache/models/auth) |
| [diagrams/user-flow.mmd](diagrams/user-flow.mmd) | End-user journey — auth (signin/signup/forgot/approval) → chat → offers → confirm → dedupe |

## Phase plans

Each phase is a **fully functional end-to-end increment**: after every phase the product runs and is demo-able. New tools/features are added behind configuration and adapter interfaces — never by rewriting the core graph.

| Phase | Name | End-to-end slice delivered |
|---|---|---|
| [0](phases/phase-0-foundation.md) | Foundation / Walking Skeleton ✅ | Thin request path: UI → API → stub agent → persisted response |
| [1](phases/phase-1-agentic-core.md) | Local Agentic Core (IIT baseline) ✅ | Streamlit + LangGraph + 3 tools + SQLite; full local demo |
| [2](phases/phase-2-retrieval-grounding.md) | Retrieval & Grounding ✅ | Real ingestion, chunking, embeddings, hybrid search, rerank, citations |
| [3](phases/phase-3-security-cloud.md) | Security & Cloud ✅ (local slice) | JWT auth, audit log, cloud-backend boundaries, Bedrock guardrail/model wiring, security suite |
| [4](phases/phase-4-experience.md) | Production Experience ✅ (local slice) | Angular 21 UI, streaming UX, feedback, multilingual param, analytics API + dashboard |
| [5](phases/phase-5-expansion.md) | Expansion ✅ (local slice) | Voice (Web Speech), Genesys agent-assist endpoint, CRM read tool, third department via config only |
| [6](phases/phase-6-pilot-readiness.md) | Pilot Readiness ✅ (local slice) | CRM writes w/ full safety contract, dept cost attribution + funnel + unmet-need clustering, dept-owner self-service views |
| [7](phases/phase-7-hardening.md) | Hardening & Handoff ✅ (local slice) | Self-service knowledge upload, P95 latency evidence, CRM/finance eval coverage, OpenAPI export + demo script |
| [8](phases/phase-8-quality-completeness.md) | Quality & Completeness ✅ (local slice) | Bedrock protocol parity, FR-16 query rewriting, conversation export, rubric scoring, real cost pricing, CI gate |
| [9](phases/phase-9-production-readiness.md) | Production Readiness ✅ (core live) | HF LLM + semantic embeddings **connected & verified**, real Redis cache, real DynamoDB store (moto-tested), Supabase/JWT auth, HF MCP |

## Current status (what's live vs pending)

| Area | Status |
|---|---|
| LangGraph agent, tools, citations, writes+confirm+dedupe | ✅ Live locally + on the public demo |
| Hugging Face provider (Llama-3.1-8B + MiniLM embeddings) | ✅ Connected locally — real token in `.env.local`, verified end-to-end |
| Public demo (Streamlit Cloud + Render) | ✅ Live — intentionally `stub` auth + local model so evaluators click through |
| Supabase Auth (signup/signin/forgot, admin-assigns) | ⚙️ Verified end-to-end on a live project — profiles table + RLS migrated, GoTrue signup/signin/token issue proven, ES256 JWKS served. **Pending**: `sb_secret_` key from the dashboard for runtime profile writes (enable `REGINTEL_AUTH_MODE=supabase` after setting it) |
| JWT auth mode | ✅ Verified locally (401 forged / 200 valid) — off on demo by design |
| DynamoDB store | ✅ **Live on DynamoDB Local** (docker :8002) — tickets/messages/feedback/jobs land in real tables; verified via API + boto3 scans. AWS RDS creds to go cloud |
| Redis cache | ✅ **Live on local redis-server** (:6379) — `kb:*` keys with 300s TTL, tamper-test proved Redis reads, 0.246s miss / 0.001s hit. `REGINTEL_REDIS_URL` swap for managed |
| Bedrock LLM/embeddings/guardrail | 🔌 Adapter boundary implemented — **pending**: AWS account + model IDs |
| Genesys agent-assist / OpenText ingestion | 🔌 Boundary only — endpoint + adapters exist, real integrations deferred (OQ-01/OQ-02) |
| Angular UI (`ui/web`) | ✅ Builds clean + serves on :4200 — CORS verified against the API; intentionally not deployed |
| `scripts/hf_refresh_token.py` | ✅ OAuth fallback for HF inference — superseded by the permanent API token |

Also: [demo-script.md](demo-script.md) — repeatable evaluator walkthrough ·
[e2e-test-checklist.md](e2e-test-checklist.md) — manual question→expected-answer matrix for all three use cases ·
[SUBMISSION.md](SUBMISSION.md) — requirement→artifact checklist ·
[pitch-deck.md](pitch-deck.md) — slide source for `submission/RegIntel-AI-Pitch-Deck.pptx`.

## Guiding principle

> Build a locally demonstrable Agentic AI assistant first; add enterprise integrations through configuration and adapters without changing the core LangGraph workflow.

Phase 1 is the **mandatory IIT Project 3 baseline** — it must pass all official scenarios locally. Later phases are gated on it.
