# Phase 6 — Pilot Readiness

**Goal:** close the deferred Phase 5 scope that is deliverable locally — CRM writes with the full safety contract, advanced analytics, department-owner self-service — and prepare the business-owner pilot review.

## End-to-end slice after this phase

An employee can create a CRM case conversationally with the identical safety contract as ticket creation; admins see cost attribution, adoption funnel, and clustered unmet needs; department owners can inspect their use case's config, sources, and access rules.

## Scope

### CRM write path (completes FR-24)
- `crm_case_create` tool behind `CRMAdapter.create_case`
- Full write-safety checklist: field validation → duplicate check → explicit confirmation → idempotent write → audit record
- Enabled per use case via the same server-side tool allowlist
- `LocalCRMAdapter` persists to the seed file; Salesforce/Dynamics adapters slot in at the same seam (OQ-04)

### Advanced analytics (FR-25 extension)
- Cost attribution by department (tokens + cost joined through employee department)
- Adoption funnel: active users → conversations → messages → feedback
- Unmet-need clustering: not-found queries grouped by shared dominant terms — the knowledge manager's content-gap signal

### Department-owner self-service (FR-27 extension)
- `GET /v1/admin/usecases` — all use cases: tools, guardrails, access rules
- `GET /v1/admin/usecases/{id}` — full config + indexed documents + usage for one use case

### Pilot-readiness checklist (doc-only)
- Security suite green; eval suite green; demo script validated; open questions (OQ-01..05) documented for the business owner

## Exit criteria

- [x] CRM write passes the full safety checklist (validation/duplicates/confirmation/idempotency/audit)
- [x] Analytics exposes department cost attribution, adoption funnel, unmet-need clusters
- [x] Department owners can inspect their use case config + sources via API
- [ ] Business owner pilot approval — external sign-off, not code

## Explicitly out of scope

- Real CRM/Genesys/OpenText/Entra/AWS provisioning — all credential-gated (OQ-01..05)
- Production deployment + P95 measurement
