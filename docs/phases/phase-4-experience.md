# Phase 4 — Production Experience

**Goal:** the production-oriented user experience — Angular web app, polished streaming UX, feedback, multilingual, analytics dashboard. Backend contract already exists from P3; this phase is mostly client-side.

## End-to-end slice after this phase

An employee uses the Angular app: sign-in via Entra ID, real-time streamed answers with tool-activity indicators, expandable citations, feedback controls, language selection. An analyst opens the dashboard: usage, quality, feedback, latency, retrieval, cost — sliced by date/model/department/use case.

## Scope

### Angular 21 app (FR-28)
- TypeScript + Tailwind CSS; Entra ID login flow (MSAL)
- Chat: streamed tokens, status/tool-activity indicators, expandable citation cards (title, source, page/section, excerpt, link — permission-filtered), feedback controls, error states, retry
- Conversation management: list, rename, archive, resume (FR-04)
- Language selector (FR-22) — detection or explicit selection; response in selected language with citations preserved
- Accessibility: keyboard nav, contrast, focus visibility, screen-reader labels (NFR-09)

### Feedback loop completion (FR-20)
- Feedback UI → API → linked to message/conversation/trace; feeds eval + analytics

### Analytics dashboard (FR-25)
- Aggregates: usage, rubric quality, feedback, latency, errors, cost by date/model/department/use case
- Tenant/department scoping on `GET /v1/admin/analytics`
- Knowledge-manager view: failed retrievals / not-found queries (drives content curation)

### Streamlit retained
- Still the evaluator/admin/demo tool; Angular is the end-user surface

## Out of scope

Voice, Genesys CX integration, CRM, additional-department onboarding at scale.

## Status: ✅ local slice implemented

| Area | Shipped | Enterprise gap |
|---|---|---|
| Angular 21 app (`ui/web/`) | Chat (NDJSON streaming via fetch/ReadableStream), tool-activity node trace, expandable citation cards, feedback buttons, conversation list/resume/rename, language selector, analytics page; Tailwind v4 styling; stub + JWT auth headers | MSAL/Entra login flow (uses bearer-token input today) |
| Feedback loop (FR-20) | UI → `POST /v1/messages/{id}/feedback` → analytics aggregation | — |
| Analytics (FR-25) | `GET /v1/admin/analytics`: totals, tokens, avg latency, feedback ratio, per-use-case usage, daily counts, not-found queries, recent feedback, recent audit | department/tenant scoping rides on Entra claims in cloud mode |
| Multilingual (FR-22) | `language` param on send → model boundary; local model discloses English-only, Bedrock model translates with citations preserved; usage records language | OQ-04 language list to confirm |
| Not-found tracking | `knowledge_not_found` audit records → knowledge-manager gap view | — |

## Exit criteria

- [x] Angular chat runs against the local backend end-to-end (stream, citations, feedback, conversations)
- [x] Dashboard shows usage/feedback/latency/not-found dimensions; feedback appears in analytics
- [x] Language selection works; evidence meaning preserved (citations stay original-language)
- [x] Streamlit local demo still runs unchanged
- [ ] UJ-01..UJ-06 pass in Angular against the **cloud** backend — needs deploy
- [ ] Accessibility checklist verified — basic landmarks/labels/focus states present; formal a11y audit pending
- [ ] Entra MSAL sign-in — pending Entra app registration

## Key risks

- Multilingual quality varies — scope to an agreed language list (OQ-04); keep citations from original-language sources
- Streaming UX edge cases (reconnects, mid-stream errors) — event protocol already defines error events; test interrupted streams
