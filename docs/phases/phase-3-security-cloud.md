# Phase 3 — Security & Cloud

**Goal:** the same product, now authenticated, streaming, and running on AWS with managed services. Core graph unchanged — every swap happens behind the interfaces built in P0–P2.

## End-to-end slice after this phase

A user signs in with Entra ID → FastAPI validates JWT → requests stream responses (status → tokens → citations → usage → complete) → conversations/config/tickets live in DynamoDB → Redis caches config + safe retrievals → Bedrock guardrails active → deployable via Lambda + API Gateway → security/adversarial suite green.

## Scope

### AuthN/AuthZ (FR-01, FR-02)
- Microsoft Entra ID app registration; JWT validation: issuer, audience, signature, expiry, required claims — on **every** request
- Claim → department/use-case/source permission mapping; filters injected server-side; never prompt-overridable
- Stub identity provider retained for local mode (config switch)

### Streaming API (FR-19)
- `POST /v1/conversations/{id}/messages:stream`: event protocol — `status`, `token`, `citation`, `usage`, `complete`, `error`
- Streamlit consumes the same stream for local demo; contract tests pin the event schema

### Cloud stores
- DynamoDB: USECASE (versioned config: active + history), CONVERSE (conversations/messages/feedback/usage), TICKETS — same repository interfaces as SQLite
- Redis: config cache + eligible retrieval responses, TTL, tenant/use-case keys, invalidation path (FR-21)
- S3 for document artifacts (from P2)

### Models & guardrails (FR-18)
- Bedrock wiring: Sonnet 4.5 generation, Haiku 4.5 enrichment, Titan/Cohere embeddings, Cohere Rerank — all model IDs config-resolved with fallback list (OQ-05)
- Bedrock guardrails + application policies: injection, harmful content, sensitive-data leakage, off-domain; blocked responses clearly communicated
- Token limits + per-request cost accounting

### Deployment & observability
- Lambda + API Gateway packaging (Mangum or equivalent); stateless backend (NFR-05)
- Structured logs + correlation IDs end-to-end; metrics/traces/alarms; no sensitive payloads in logs (NFR-07)
- P95 targets validated: first token ≤4s, answer ≤12s (NFR-04)
- Separate dev/test/prod config; audit records: actor, action, config/model versions, evidence, outcome (NFR-12)

### Security test suite (NFR-08)
- Adversarial cases: prompt injection via documents, cross-department retrieval attempts, unauthorized tool calls, forged/expired JWTs, missing claims → 100% blocked/contained

## Out of scope

Angular UI, multilingual, voice, Genesys CX integration, CRM.

## Exit criteria

- [ ] Authenticated end-to-end cloud flow passes security tests
- [ ] JWT rejected without crypto validation + issuer/audience checks (tests prove it)
- [ ] Streaming events consumed by UI; P95 targets measured and met
- [ ] DynamoDB/Redis/Bedrock swap via config only — local mode still works for evaluators
- [ ] Deployed to approved AWS environment; smoke test green; rollback path documented
- [ ] OQ-01 answered: deploy target confirmed (pure AWS vs Genesys Cloud integration path)

## Key risks

- Entra app registration / AWS roles are enterprise dependencies — request early, keep stub mode working
- Bedrock model availability by region — config-resolved model IDs + approved substitutes (OQ-05)
