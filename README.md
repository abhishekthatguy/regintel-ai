# RegIntel AI

Enterprise Knowledge & Operations Assistant — IIT Patna GenAI Development Program, Project 3.

A configuration-driven agentic assistant: employees ask questions, get evidence-grounded answers with citations, look up and create IT tickets — orchestrated by LangGraph. See `docs/` for the full knowledge base and phase plan.

## Status

**Phase 1 — Local Agentic Core (IIT Project 3 baseline).** LangGraph agent with 3 tools (knowledge search, ticket lookup, ticket create) behind conditional routing; multi-turn state via SQLite checkpointer; clarify → duplicate-check → confirm → create flow; citations; feedback; guardrails; Streamlit chat + admin + eval pages; 21-case golden suite.

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
  api/        FastAPI routes (health, conversations, streaming, feedback)
  agent/      AgentRunner protocol, stub, LangGraphRunner + graph (all §9 nodes)
  config/     UseCaseLoader — versioned YAML use-case config (DynamoDB in P3)
  guardrails/ input/output checks (injection, sensitive data)
  identity/   IdentityProvider protocol + stub (Entra ID/JWT in P3)
  llm/        ChatModel protocol + deterministic local model (Bedrock in P3)
  retrieval/  corpus loader + BM25 index (OpenSearch hybrid in P2)
  schemas/    Pydantic contracts: Message, Conversation, Citation, AgentState,
              ToolResult, UseCaseConfig, StreamEvent
  stores/     SQLiteStore: conversations, messages, tickets, feedback (DynamoDB in P3)
  tools/      knowledge_search, ticket_lookup, ticket_create behind ToolContext
  middleware.py   correlation-ID middleware
  logging_config.py  JSON logs + sensitive-field redaction
ui/
  streamlit_app.py  chat UI: streamed answers, citations, tool trace, feedback
  pages/2_Admin.py  use-case config + data inspection (FR-27)
  pages/3_Eval.py   golden-suite runner + report (FR-26)
data/
  knowledge/  sample corpus (IT + HR markdown with metadata front-matter)
  usecases/   versioned use-case configs (it_support, hr_support)
  seed/       demo employees + tickets
eval/         golden_cases.json + rubric runner
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
| `POST /v1/conversations/{id}/messages:stream` | Send message → NDJSON event stream (`status`, `token`, `citation`, `usage`, `complete`, `error`) |
| `PATCH /v1/conversations/{id}` | Rename (`title`) or archive (`status`) a conversation |
| `POST /v1/messages/{id}/feedback` | Thumbs rating + reason + comment, linked to message/conversation |
| `POST /v1/admin/ingestions` | Start an ingestion job (`admin` role; body: `{source: local_files\|opentext\|msgraph}`) |
| `GET /v1/admin/ingestions` / `/{job_id}` | Ingestion job status + dead-lettered failures |

Demo identity via `X-Demo-Employee: e001|e002|e999` header — **stub only**, replaced by Entra ID JWT validation in Phase 3. `e999` carries the `admin` role.

## Notes / limitations (Phase 2)

- LLM is a deterministic local implementation (`app/llm/local.py`) — grounded answers are composed extractively from retrieved chunks. A real provider (Bedrock Claude) plugs in via `REGINTEL_LLM_PROVIDER` in Phase 3.
- Retrieval is local hybrid: BM25 + deterministic hashing-vector cosine merged via reciprocal-rank fusion, then `LocalReranker` rescoring (`app/retrieval/`). OpenSearch + Bedrock Titan/Cohere swap in via `models.embedding`/`models.rerank` config in Phase 3.
- Ingestion pipeline (`app/ingestion/`): `SourceAdapter` interface with local-files adapter live and OpenText/Graph skeletons that fail closed; checksum drift detection re-indexes changed docs; per-doc failures land in the `ingestion_failures` dead-letter table.
- Citations carry the full §10.1 contract: document, section, chunk, excerpt, retrieval + rerank scores, version, source URL/ref, access decision.
- Auth is a demo header (`X-Demo-Employee`), not real authentication — Entra ID in Phase 3.
- Multi-turn state persists in the SQLite checkpointer; per-employee ticket scoping is enforced server-side.
