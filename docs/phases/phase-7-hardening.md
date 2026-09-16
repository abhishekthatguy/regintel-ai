# Phase 7 — Hardening & Handoff

**Goal:** close the remaining locally-deliverable gaps before the pilot
review — self-service content onboarding, measured latency evidence,
eval coverage for the new journeys, and handoff artifacts.

## End-to-end slice after this phase

A department owner uploads a markdown doc via API and it becomes retrievable
(with citations) in the same request path; P95 latency is measured against
NFR targets; the golden suite covers CRM + finance journeys; an OpenAPI
export and a scripted evaluator demo exist.

## Scope

### Self-service knowledge upload (FR-10/FR-27)
- `POST /v1/admin/knowledge` — markdown + front-matter upload, validated
  (doc_id pattern, required fields, ACL list, filename safety), written to
  the department corpus dir, re-ingested via the checksum pipeline, audited
- Retrieval picks it up immediately (per-call retriever, no cache to bust)

### Performance evidence (NFR latency targets)
- `scripts/load_test.py` — concurrent streamed conversations, reports
  p50/p95 for first-token and full-answer latencies vs ≤4s / ≤12s targets

### Eval coverage (FR-26)
- Golden cases extended to CRM lookup/create/cancel/scope and the Finance
  department (routing, ACL, citation contract)

### Handoff artifacts
- `scripts/export_openapi.py` — OpenAPI JSON for Postman/import
- `docs/demo-script.md` — repeatable evaluator walkthrough

## Exit criteria

- [x] Uploaded doc is retrievable with citations in one request path
- [x] Local P95 measured and documented (first-token 0.065s, answer 0.070s on the local model)
- [x] Golden suite covers CRM + finance journeys (31 cases)
- [x] OpenAPI export + demo script committed
- [ ] Business owner pilot approval — external sign-off

## Out of scope

- Real cloud P95 measurement (needs the AWS deployment)
- LLM-judge rubric dims (needs a configured judge model)
