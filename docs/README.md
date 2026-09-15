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

## Guiding principle

> Build a locally demonstrable Agentic AI assistant first; add enterprise integrations through configuration and adapters without changing the core LangGraph workflow.

Phase 1 is the **mandatory IIT Project 3 baseline** — it must pass all official scenarios locally. Later phases are gated on it.
