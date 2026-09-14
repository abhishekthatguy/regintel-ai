# Decisions & Open Questions

## Resolved decisions

| # | Decision | Resolution | Implementation impact |
|---|---|---|---|
| D-01 | What "OpenText" means | OpenText is the enterprise **secure information management for AI** platform (Content Management / Extended ECM family) | It's a **pluggable ingestion source** behind an adapter interface (FR-10). POC ships a local-file/mock adapter; real integration uses OpenText REST APIs later. The adapter contract must anticipate OpenText metadata: ACLs, versions, source IDs |
| D-02 | What "Genis Cloud" means | **Genesys Cloud** — the agentic AI / CX platform for enterprise (genesys.com) | Genesys Cloud is not a general-purpose host; it runs on AWS and exposes integration surfaces (data actions, bot connectors, agent assist). Read BRD §18 as: service deploys on AWS (Lambda/API Gateway) and **integrates into Genesys Cloud CX via its APIs**. Exact surface still TBD — see OQ-01 |
| D-03 | What "Rubrics" means | A **generic scoring framework** — criteria + performance levels describing what performance looks like at each level | No vendor dependency. FR-26 is a custom rubric-scored eval runner (golden dataset + LLM-as-judge/human ratings). See [evaluation-framework.md](evaluation-framework.md) |

## Open questions (to confirm with document owner / during discovery)

| # | Question | Why it matters | Blocks |
|---|---|---|---|
| OQ-01 | Is the Genesys deliverable a real Genesys Cloud CX integration (bot/agent-assist via Genesys APIs, needs OAuth client + test org) or just "AWS deploy in a Genesys-approved environment"? | Very different scopes; real CX integration needs Genesys org access | Phase 5 (possibly Phase 3 deploy target) |
| OQ-02 | Which OpenText product + API exactly (Content Server REST API, Extended ECM, Core Content)? | Determines adapter auth model, metadata schema, and whether a sandbox is available | Phase 2 adapter build-out |
| OQ-03 | Primary embedding model choice + re-index strategy when models change | Vector dimension/model lock-in; re-index cost | Phase 2 |
| OQ-04 | Supported languages, voice provider, CRM target | Shapes Phase 4/5 scope | Phases 4–5 |
| OQ-05 | Which Bedrock region/account exposes the selected models or approved substitutes | Model IDs resolved by config; need fallback list | Phase 3 |

## Standing assumptions (from BRD §20)

- POC uses synthetic/non-sensitive sample data and approved enterprise documents
- One Bedrock region/account exposes the selected models or approved substitutes
- Entra app registration, Graph permissions, AWS roles and source-system access are dependencies provided by the enterprise
- Department owners provide metadata taxonomy and evaluation questions

## Key risks (from BRD §19)

| Risk | Mitigation |
|---|---|
| Scope overload | IIT Core is the mandatory baseline; gate later phases |
| Model/version availability | Resolve model IDs by config; support approved fallbacks |
| Access-control leakage | Server-side claim filters, adversarial tests, least privilege |
| Hallucinated answers | Evidence threshold, citations, grounded prompt, not-found response |
| Prompt injection in documents | Untrusted-content isolation, tool allowlists, guardrails |
| Duplicate side effects | Confirmation, idempotency keys, duplicate lookup |
| Cost growth | Model routing, token limits, caching, budgets, cost attribution |
| Source drift | Version/checksum tracking, scheduled sync, delete propagation |
