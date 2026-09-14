# Phase 5 — Expansion

**Goal:** extend reach — voice, Genesys Cloud CX integration, CRM tools, additional departments. All additive via existing adapter/tool/config seams; no core-graph changes.

## End-to-end slice after this phase

Voice in/out with retained transcripts; the assistant surface available inside Genesys Cloud CX (per OQ-01 resolution); approved CRM read/write tools with confirmation + audit; a third department live via config + content only.

## Scope

### Voice (FR-23)
- Speech input/output in the UI; text transcript always retained and fed to the same pipeline
- Voice provider TBD (OQ-04) behind a `SpeechProvider` interface

### Genesys Cloud CX integration (pending OQ-01)
- Likely surfaces: **data action** calling our API from agent flows, **bot connector**, or **agent-assist/copilot** embedding
- Requires: Genesys OAuth client, test org, integration approval — enterprise dependency
- Keep the standalone web/app path fully functional regardless

### CRM adapter (FR-24)
- `CRMAdapter` interface; approved read/write tools exposed to the graph
- Same safety contract as ticket creation: validated inputs, idempotency, explicit confirmation, audit record
- CRM target TBD (OQ-04)

### Multi-department scale
- Onboard additional departments/use cases: config + metadata + indexed content only — the acceptance test for the whole configurability thesis (UJ-07)
- Department-owner self-service views: sources, prompts, tools, access rules

### Advanced analytics
- Cost attribution refinement, adoption funnels, unmet-need clustering from not-found queries

## Exit criteria

- [ ] Voice I/O works; transcript preserved; citations still shown
- [ ] Genesys integration demo path working (or documented decision if scope = AWS-only)
- [ ] CRM tool passes the full write-safety checklist (validation/duplicates/confirmation/idempotency/audit)
- [ ] Third department enabled with zero new business logic
- [ ] Pilot readiness review + business owner approval

## Key risks

- Genesys scope ambiguity (OQ-01) — resolve before planning this phase in detail
- CRM/voice provider decisions (OQ-04) are external dependencies
- Enterprise access lead times — these all need real orgs/credentials, unlike earlier phases
