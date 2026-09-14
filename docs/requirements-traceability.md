# Requirements Traceability

Every BRD requirement mapped to the phase that delivers it. "P1 basic" means a local functional version; the full enterprise form lands in the phase shown second.

## Functional requirements

| ID | Capability | Priority | Phase |
|---|---|---|---|
| FR-01 | Entra ID authentication, JWT validation | Must | P3 (P1: stub identity) |
| FR-02 | Claim → department/use-case/source authorization | Must | P3 (P1: stub user roles) |
| FR-03 | Versioned USECASE/CONVERSE config w/ defaults + validation | Must | P1 (file/SQLite) → P3 (DynamoDB) |
| FR-04 | Conversation CRUD: create/retrieve/continue/rename/archive | Must | P1 |
| FR-05 | LangGraph state: messages, user, use case, intent, filters, tools, citations, pending action, errors | Must | P1 |
| FR-06 | Routing: direct/search/lookup/create/clarify/refusal/failure | Must | P1 |
| FR-07 | Knowledge search tool, ranked evidence + source metadata | Must | P1 (local corpus) → P2 (full pipeline) |
| FR-08 | Ticket lookup, authorized, no invented values | Must | P1 |
| FR-09 | Ticket creation: field validation, duplicate check, confirmation, unique record | Must | P1 |
| FR-10 | Ingestion via replaceable source adapters (Graph, OpenText) | Should | P2 (local adapter P1) |
| FR-11 | Document-aware contextual chunking w/ source, page/section, dept, ACL, version | Must | P2 |
| FR-12 | Titan Embed v2 / Cohere Embed v3 by config | Must | P2 (P1: local embeddings option) |
| FR-13 | OpenSearch hybrid semantic+keyword w/ metadata/ACL filters | Must | P2 |
| FR-14 | Cohere Rerank + relevance thresholds | Must | P2 (P1: simple scorer) |
| FR-15 | Claude Sonnet 4.5 generation, evidence-only claims | Must | P1 |
| FR-16 | Claude Haiku 4.5 for rewriting/context/classification | Should | P2 |
| FR-17 | Citation IDs on claims; title, source, page/section, excerpt, link | Must | P1 (basic) → P2 (full contract) |
| FR-18 | Input/output guardrails, clear blocked-response messaging | Must | P3 (P1: basic app-level checks) |
| FR-19 | Streamed status/tokens/citations/usage/complete-error events | Should | P3 (P1: Streamlit-native rendering) |
| FR-20 | Feedback: thumbs + reason + comment, linked to IDs | Must | P1 |
| FR-21 | Redis cache w/ TTL, tenant/use-case keys, invalidation | Should | P3 |
| FR-22 | Multilingual detection/selection, meaning preserved | Could | P4 |
| FR-23 | Optional speech I/O w/ text transcript retained | Could | P5 |
| FR-24 | CRM read/write adapter w/ confirmation + audit | Phase 2* | P5 |
| FR-25 | Analytics dashboard: usage/quality/feedback/latency/errors/cost by dims | Should | P4 (P1: basic metrics log) |
| FR-26 | Eval runner: retrieval, groundedness, relevance, completeness, citations, tool selection | Must | P1 → grows each phase |
| FR-27 | Streamlit admin/demo/eval/trace UI | Must | P1 |
| FR-28 | Angular 21 + TS + Tailwind end-user UI | Should | P4 |

*FR-24 is labeled "Phase 2" in the BRD but refers to the enterprise delivery timeline; in our plan it lands in expansion phase P5.

## Non-functional requirements

| ID | Area | Phase |
|---|---|---|
| NFR-01 | Security (TLS, encryption at rest, least-privilege IAM, secrets out of source) | P0 (secrets) → P3 (full) |
| NFR-02 | Privacy (no cross-user/dept exposure, redacted logs) | P3 |
| NFR-03 | Availability (bounded retries, clear errors) | P1 |
| NFR-04 | Performance (P95 targets, streaming progress) | P3–P4 |
| NFR-05 | Scalability (stateless backend, independent stores) | P3 |
| NFR-06 | Maintainability (typed contracts, adapters, modular nodes, config-driven) | P0–P1 |
| NFR-07 | Observability (structured logs, correlation IDs, metrics, traces) | P0 → enriched per phase |
| NFR-08 | Quality (repeatable unit/integration/contract/retrieval/rubric suites) | P1 → CI per phase |
| NFR-09 | Accessibility (keyboard, contrast, focus, screen-reader) | P4 |
| NFR-10 | Portability (local run w/ SQLite/mocks + one LLM provider) | P1 |
| NFR-11 | Resilience (idempotent writes/ingestion, transient-only retries, DLQ) | P1 (tickets) → P2 (ingestion) |
| NFR-12 | Auditability (config/model versions, sources, tool calls, confirmations) | P1 → P3 |

## IIT Project 3 traceability (BRD Appendix A)

| Official expectation | Covered by |
|---|---|
| Python-first, local, achievable | Phase 1: SQLite + Streamlit + one configured LLM provider |
| ≥3 tools | Knowledge Search, Ticket Lookup, Ticket Creation (P1) |
| LangGraph state/nodes/edges/routing | FR-05, FR-06, agent spec (P1) |
| Multi-turn memory | FR-04, FR-05 (P1) |
| Validation + duplicate prevention | FR-09 (P1) |
| Graceful failures, no invented ticket data | Error node, rubric tests (P1) |
| Streamlit interface | FR-27 (P1) |
| Modular code, README, samples, GitHub | P0–P1 |
| Understand → Design → Implement → Test → Explain | Phased delivery, rubrics, demo deliverables |
