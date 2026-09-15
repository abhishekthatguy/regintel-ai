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

**Angular app** (Phase 4 end-user surface):

```bash
cd ui/web && npm install && npx ng serve
```

Open http://localhost:4200 — chat with streaming + citations + feedback + language selector, `/analytics` for the admin dashboard (sign in as e999).

## Test

```bash
.venv/bin/pytest          # test suite
.venv/bin/ruff check .    # lint
```

## Layout

```
app/
  api/        FastAPI routes (health, conversations, streaming, feedback, admin)
  agent/      AgentRunner protocol, LangGraphRunner + graph (all §9 nodes)
  config/     UseCaseLoader — versioned YAML use-case config (DynamoDB boundary)
  guardrails/ input/output checks + Bedrock ApplyGuardrail boundary
  identity/   IdentityProvider protocol + stub + JWT (HS256 dev / Entra JWKS)
  ingestion/  SourceAdapter (local files live, OpenText/Graph skeletons) + pipeline
  llm/        ChatModel protocol + local model + BedrockChatModel
  retrieval/  BM25 + hashing-vector hybrid (RRF) + reranker (OpenSearch/Bedrock swap)
  schemas/    Pydantic contracts: Message, Conversation, Citation, AgentState,
              ToolResult, UseCaseConfig, StreamEvent
  stores/     SQLiteStore + DynamoDBStore skeleton; audit_log, chunks, jobs
  tools/      knowledge_search, ticket_lookup, ticket_create behind ToolContext
  audit.py    NFR-12 audit records; cache.py FR-21 cache boundary
  lambda_handler.py  Mangum entry point for Lambda + API Gateway
  middleware.py   correlation-ID middleware
  logging_config.py  JSON logs + sensitive-field redaction
ui/
  streamlit_app.py  chat UI: streamed answers, citations, tool trace, feedback
  pages/2_Admin.py  use-case config + data inspection (FR-27)
  pages/3_Eval.py   golden-suite runner + report (FR-26)
  web/            Angular 21 end-user app (chat, citations, feedback, analytics)
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
| `GET /v1/admin/analytics` | Usage/feedback/latency/not-found aggregates (`admin` role) |

Demo identity via `X-Demo-Employee: e001|e002|e999` header in stub mode (`e999` carries the `admin` role). With `REGINTEL_AUTH_MODE=jwt`, every request needs a Bearer JWT validated for signature/issuer/audience/expiry — mint a dev token via `scripts/mint_dev_token.py` (requires `REGINTEL_JWT_SECRET`); Entra JWKS validation plugs in via `REGINTEL_JWT_JWKS_URL`.

## Notes / limitations (Phase 4)

- LLM is a deterministic local implementation (`app/llm/local.py`) — grounded answers are composed extractively from retrieved chunks. Bedrock Claude plugs in via `REGINTEL_LLM_PROVIDER=bedrock` (Converse API; self-degrades to local without credentials).
- Retrieval is local hybrid: BM25 + deterministic hashing-vector cosine merged via reciprocal-rank fusion, then `LocalReranker` rescoring (`app/retrieval/`). OpenSearch + Bedrock Titan/Cohere swap in via `models.embedding`/`models.rerank` config.
- Ingestion pipeline (`app/ingestion/`): `SourceAdapter` interface with local-files adapter live and OpenText/Graph skeletons that fail closed; checksum drift detection re-indexes changed docs; per-doc failures land in the `ingestion_failures` dead-letter table.
- Citations carry the full §10.1 contract: document, section, chunk, excerpt, retrieval + rerank scores, version, source URL/ref, access decision.
- Auth is a demo header (`X-Demo-Employee`) in stub mode; JWT mode does real crypto validation locally (HS256 dev key) or Entra RS256 via JWKS.
- Cloud backends are boundaries: `REGINTEL_STORE_BACKEND=dynamodb`, `REGINTEL_CACHE_BACKEND=redis`, `REGINTEL_LLM_PROVIDER=bedrock`, `REGINTEL_GUARDRAIL_ID` all fail closed or degrade to local until credentials exist. `app/lambda_handler.py` provides the Lambda entry point.
- Security-relevant actions write to the `audit_log` table (actor, action, outcome, config context).
- Angular app (`ui/web/`) is the end-user surface; Entra MSAL login swaps in once the app registration exists (bearer-token input today). Multilingual selection is recorded and routed to the model boundary — the local model discloses English-only.
- Multi-turn state persists in the SQLite checkpointer; per-employee ticket scoping is enforced server-side.
