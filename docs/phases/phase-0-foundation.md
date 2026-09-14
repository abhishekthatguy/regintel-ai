# Phase 0 — Foundation / Walking Skeleton

**Goal:** a thin, working end-to-end request path plus all project plumbing — so Phase 1 work is purely additive.

## End-to-end slice after this phase

User types a message in a minimal Streamlit page → request travels through the backend entry point → a stub agent echoes a canned response → conversation + request logged with correlation ID → response displayed. Nothing intelligent yet, but every layer exists and is wired.

## Scope

### Repo & plumbing
- Repository layout: `app/` (api, agent, tools, retrieval, stores, config, schemas), `ui/` (streamlit), `tests/`, `data/` (sample content), `docs/` (this KB), `scripts/`
- `pyproject.toml` / dependency management, pinned versions
- `.env.example` with placeholders only; `python-dotenv` loading; secrets never committed
- Structured logging with correlation ID middleware; log redaction list
- Pydantic domain contracts: `Message`, `Conversation`, `AgentState`, `Citation`, `ToolResult`, `UseCaseConfig`
- Config loader: USECASE config from local YAML/SQLite with defaults + validation errors

### Backend skeleton
- FastAPI app with `GET /health`, `GET /ready`
- `POST /v1/conversations` + `POST /v1/conversations/{id}/messages:stream` routed to a **stub agent runner** (single node returning a fixed response)
- SQLite persistence: conversations + messages tables
- Stub identity provider (returns a fixed test user) behind an `IdentityProvider` interface

### UI skeleton
- Streamlit page: conversation list, message input, rendered response, correlation ID shown in a debug expander

### DevOps skeleton
- GitHub repo, protected `main`, PR flow
- CI: lint + typecheck + pytest on every PR (artifact/security gates come later)
- README: setup, env vars, run commands

### Sample data
- ~10 synthetic knowledge docs (markdown) across 2 departments (IT, HR) with front-matter metadata: `doc_id, title, department, acl, version`
- `employees` + `tickets` seed tables for Phase 1 tools

## Out of scope this phase

Any real LLM call, retrieval, tool logic, auth, streaming events beyond a single final response.

## Exit criteria

- [ ] `uvicorn` + `streamlit` start with one documented command each
- [ ] Message sent in UI → stub response → row in SQLite → correlation ID in logs and UI
- [ ] `pytest` green in CI; lint/typecheck clean
- [ ] `.env.example` complete; no secrets in repo

## Test baseline

- Contract tests for Pydantic schemas; health/readiness endpoint tests; config loader validation tests; persistence round-trip test.
