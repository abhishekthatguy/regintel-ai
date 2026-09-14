# Architecture

## Design principles

1. **Local-first, adapter-based** — the LangGraph core never changes between local demo and enterprise deployment. Infra concerns (auth, stores, models, sources) live behind interfaces resolved by configuration.
2. **Config-driven use cases** — department/use-case behavior (prompts, models, tools, filters, guardrails, cost tags) is data in a USECASE store, not code.
3. **Grounded or silent** — the agent answers only from retrieved evidence or explicitly says evidence was not found.
4. **Safe writes** — every state-changing tool validates inputs, checks duplicates, requires explicit confirmation, and is idempotent.

## Request data flow (11 stages)

| # | Stage | Requirement |
|---|---|---|
| 1 | Authenticate | UI obtains Entra ID token; API validates JWT + claims (local phase: stub identity) |
| 2 | Configure | Load tenant/department/use-case/model/tool/prompt/guardrail config |
| 3 | Interpret | LangGraph updates conversation state; selects direct / retrieval / tool path |
| 4 | Filter | Map claims → department/content metadata → mandatory access filters |
| 5 | Retrieve | Hybrid vector + keyword search; merge candidates |
| 6 | Rerank | Reranker orders candidates; threshold removes weak evidence |
| 7 | Generate | Sonnet generates grounded response; Haiku may enrich context/rewrite queries |
| 8 | Protect | Guardrails + app policies check input/output; block unsafe operations |
| 9 | Process | Extract citations, compute usage/cost/latency, format streamed events |
| 10 | Persist | Store conversation, messages, feedback, usage; cache safe results |
| 11 | Display | UI shows answer, expandable citations, tool activity, feedback, errors |

## LangGraph agent spec

| Node | Responsibility | Primary transitions |
|---|---|---|
| Initialize | Validate request; hydrate user/config/conversation state | → Classify or Error |
| Classify / Plan | Determine intent, missing info, required tool/action | → Clarify / Retrieve / Lookup / Create / Direct |
| Clarify | Ask one focused question; preserve pending action | → wait for user |
| Build Filters | Convert identity + department metadata into mandatory retrieval filters | → Retrieve |
| Retrieve + Rerank | Hybrid search, rerank, validate evidence sufficiency | → Generate or Not Found |
| Ticket Lookup | Validate scope; query ticket store | → Respond or Error |
| Duplicate Check | Find equivalent open ticket before creation | → Confirm / Existing Ticket / Error |
| Confirm Action | Require explicit confirmation for ticket creation | → Create or Cancel |
| Ticket Create | Persist validated ticket + audit record | → Respond or Error |
| Generate | Create grounded answer + structured citation markers | → Guardrail |
| Guardrail | Evaluate safety, privacy, policy compliance | → Process or Refuse |
| Process Response | Resolve citations, usage, cost; stream events | → Persist |
| Persist | Write conversation, trace summary, feedback linkage, metrics | → End |
| Error Handler | Safe actionable error + diagnostics | → End or Retry |

**Minimum demo requirement:** knowledge search, ticket lookup, and ticket creation tools visibly execute with multi-turn state, missing-field clarification, duplicate prevention, and graceful tool failure.

## Agent state

Messages, user context, use case, intent, retrieval filters, tool results, citations, pending action, errors.

## Data model

| Store | Purpose | Key fields | Phase introduced |
|---|---|---|---|
| USECASE config | Versioned assistant configuration | tenant_id, usecase_id, prompts, models, tools, filters, guardrails, cost tags | P1 (file/SQLite) → P3 (DynamoDB) |
| CONVERSE | Conversation persistence | conversation_id, user_id, messages, state, citations, feedback, usage | P1 (SQLite) → P3 (DynamoDB) |
| TICKETS | Ticket operations | ticket_id, employee_id, category, description, status, priority, timestamps | P1 (SQLite) |
| Vector index | Chunk + vector retrieval | chunk_id, text, vector, source, page, section, ACL, department, version | P1 (local) → P2 (OpenSearch Serverless) |
| Object storage | Raw/normalized docs + ingestion artifacts | object key, checksum, source ID, version, status | P2 (local dir) → P2/P3 (S3) |
| Cache | Config + eligible retrieval cache | tenant/usecase/query hash, value, TTL | P3 (Redis) |
| Logs/metrics | Observability + audit | correlation ID, actor, action, outcome, latency, tokens, cost | P0 → enriched each phase |

## Citation contract

Each citation: `citation_id, document_id, title, source_system, source_url_or_ref, page/section, chunk_id, quoted_excerpt, retrieval_score, rerank_score, document_version, user_access_decision`. UI displays only permitted fields.

## API surface

| Endpoint | Purpose |
|---|---|
| `POST /v1/conversations` | Create conversation; return ID + resolved config version |
| `POST /v1/conversations/{id}/messages:stream` | Submit message; stream status/token/citation/usage/complete/error events |
| `GET /v1/conversations/{id}` | Load conversation; owner/role auth; paginated messages |
| `POST /v1/messages/{id}/feedback` | Thumbs rating + reason + comment; linked to trace |
| `POST /v1/admin/ingestions` | Start ingestion job (admin only) |
| `GET /v1/admin/analytics` | Aggregate metrics with tenant/department/date scope |
| `GET /health`, `GET /ready` | Probes; no secrets or sensitive dependency details |

## Technology mapping

| Layer | Technology | Local (P0–P2) | Enterprise (P3+) |
|---|---|---|---|
| Backend | Python, FastAPI, Pydantic | ✓ | ✓ |
| Agent | LangGraph / LangChain | ✓ | ✓ |
| Generation | Claude Sonnet 4.5 (Nova Pro alternate) | configured provider | AWS Bedrock |
| Enrichment | Claude Haiku 4.5 | optional | AWS Bedrock |
| Embeddings | Titan Embed v2 / Cohere Embed v3 | local model option | AWS Bedrock |
| Rerank | Cohere Rerank | local/simple scorer | AWS Bedrock |
| Retrieval | OpenSearch Serverless hybrid | local BM25/embeddings + SQLite/FAISS | OpenSearch Serverless |
| Stores | DynamoDB / SQLite | SQLite | DynamoDB |
| Cache | Redis | in-process/noop | Redis |
| Compute | Lambda + API Gateway | uvicorn | Lambda + API Gateway |
| Auth | Entra ID / JWT | stub identity provider | Entra ID |
| Doc sources | Microsoft Graph / OpenText | local file adapter | Graph + OpenText adapters |
| End-user UI | Angular 21 + TS + Tailwind | — | P4 |
| Demo/admin UI | Streamlit | ✓ | ✓ |
| Eval | pytest + rubric runner | ✓ | ✓ + CI gate |
| CI/CD | GitHub → Nexus IQ → JFrog | lint+pytest skeleton | full gates |
| Hosting | Genesys Cloud CX / AWS | — | see [decisions](decisions-and-open-questions.md) |

## Security model (applies every phase, enforced fully in P3)

- JWT never accepted without cryptographic validation + issuer/audience checks
- Authorization filters injected server-side; never overridable by prompts
- Retrieved text treated as **untrusted data**, isolated from system/tool instructions
- Writes require validated inputs + idempotency + explicit confirmation
- Guardrails cover prompt injection, harmful content, sensitive-data leakage, off-domain requests
- Secrets only in env/secret management; `.env.example` has placeholders only
- Audit records capture actor, action, config/model version, evidence, outcome
