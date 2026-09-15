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

## Status: ✅ local slice implemented

Real code shipped; enterprise integrations are boundaries that fail closed until credentials/config arrive:

| Area | Shipped | Enterprise swap (needs creds) |
|---|---|---|
| Auth (FR-01/02) | `JWTIdentityProvider` — real signature/iss/aud/exp validation; HS256 dev secret locally, JWKS/RS256 for Entra; `REGINTEL_AUTH_MODE=jwt` | Entra app registration + JWKS URL |
| Stores | `DynamoDBStore` skeleton behind `REGINTEL_STORE_BACKEND`; key design documented | AWS tables + IAM |
| Cache (FR-21) | `LocalTTLCache` + `RedisCache` skeleton behind `REGINTEL_CACHE_BACKEND` | ElastiCache endpoint |
| Models (FR-18) | `BedrockChatModel` (Converse API, OQ-05 fallback list) via `REGINTEL_LLM_PROVIDER=bedrock`; self-degrades to local | Bedrock model access |
| Guardrails | Local patterns always run; Bedrock `ApplyGuardrail` merged when `REGINTEL_GUARDRAIL_ID` set | Guardrail id/version |
| Audit (NFR-12) | `audit_log` table + `record_audit` on auth failures, ticket create, ingestion runs | — |
| Deploy | `app/lambda_handler.py` (Mangum, guarded import) | Lambda + API Gateway packaging |

## Exit criteria

- [x] JWT rejected without crypto validation + issuer/audience checks (8 security tests: valid/expired/forged/wrong-iss/wrong-aud/missing-claims/missing-token/role-enforcement)
- [x] Security suite: doc-injection containment, disabled-tool invocation, audit-trail assertions — 12 cases green
- [x] Streaming events consumed by UI (existing P1 contract; citation scores added P2)
- [x] Backend swap via config only (`auth_mode`, `store_backend`, `cache_backend`, `llm_provider`) — local stub mode fully working for evaluators
- [ ] Deployed to approved AWS environment — **blocked on enterprise AWS account + Entra app registration** (request early)
- [ ] P95 targets measured — requires real cloud deploy
- [ ] OQ-01 answered: deploy target confirmed (pure AWS vs Genesys Cloud integration path) — still open

## Key risks

- Entra app registration / AWS roles are enterprise dependencies — request early, keep stub mode working
- Bedrock model availability by region — config-resolved model IDs + approved substitutes (OQ-05)
