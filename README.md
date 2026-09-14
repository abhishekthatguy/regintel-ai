# RegIntel AI

Enterprise Knowledge & Operations Assistant — IIT Patna GenAI Development Program, Project 3.

A configuration-driven agentic assistant: employees ask questions, get evidence-grounded answers with citations, look up and create IT tickets — orchestrated by LangGraph. See `docs/` for the full knowledge base and phase plan.

## Status

**Phase 0 — walking skeleton.** UI → API → stub agent → SQLite → logs with correlation IDs, all wired end-to-end. The real LangGraph agent lands in Phase 1.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"     # runtime + dev deps (pinned in pyproject.toml)
cp .env.example .env                  # then edit if needed (defaults work)
.venv/bin/python scripts/seed_db.py   # demo employees + tickets
```

## Run (two terminals)

```bash
# Terminal 1 — API
.venv/bin/uvicorn app.main:app --reload --port 8000

# Terminal 2 — Streamlit demo UI
.venv/bin/streamlit run ui/streamlit_app.py
```

Open http://localhost:8501. Pick a demo employee (header `X-Demo-Employee` carries the identity) and a use case, then chat.

## Test

```bash
.venv/bin/pytest          # test suite
.venv/bin/ruff check .    # lint
```

## Layout

```
app/
  api/        FastAPI routes (health, conversations, streaming)
  agent/      AgentRunner protocol + Phase-0 stub (LangGraph impl in Phase 1)
  config/     UseCaseLoader — versioned YAML use-case config (DynamoDB in P3)
  identity/   IdentityProvider protocol + stub (Entra ID/JWT in P3)
  schemas/    Pydantic contracts: Message, Conversation, Citation, AgentState,
              ToolResult, UseCaseConfig, StreamEvent
  stores/     SQLiteStore (DynamoDB in P3)
  middleware.py   correlation-ID middleware
  logging_config.py  JSON logs + sensitive-field redaction
ui/streamlit_app.py   demo chat UI
data/
  knowledge/  sample corpus (IT + HR markdown with metadata front-matter)
  usecases/   versioned use-case configs
  seed/       demo employees + tickets
scripts/seed_db.py
tests/
docs/         knowledge base + phase plans
```

## API

| Endpoint | Purpose |
|---|---|
| `GET /health`, `GET /ready` | Liveness / readiness probes |
| `POST /v1/conversations` | Create conversation (body: `{usecase_id?, title?}`) |
| `GET /v1/conversations` | List caller's conversations |
| `GET /v1/conversations/{id}` | Load conversation + messages (owner only) |
| `POST /v1/conversations/{id}/messages:stream` | Send message → NDJSON event stream (`status`, `token`, `usage`, `complete`, `error`) |

Demo identity via `X-Demo-Employee: e001|e002|e999` header — **stub only**, replaced by Entra ID JWT validation in Phase 3.

## Notes / limitations (Phase 0)

- Agent is a stub echo; no real retrieval, tools, or LLM calls yet.
- Auth is a demo header, not real authentication.
- Single-node local deployment only.
