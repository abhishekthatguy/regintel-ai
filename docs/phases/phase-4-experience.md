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

## Exit criteria

- [ ] UJ-01..UJ-06, UJ-08 pass in Angular against the cloud backend
- [ ] Accessibility checklist verified on primary flows
- [ ] Multilingual: response language selection works; evidence meaning preserved
- [ ] Dashboard shows all required dimensions; feedback appears in analytics
- [ ] Streamlit local demo still runs unchanged (evaluator path intact)

## Key risks

- Multilingual quality varies — scope to an agreed language list (OQ-04); keep citations from original-language sources
- Streaming UX edge cases (reconnects, mid-stream errors) — event protocol already defines error events; test interrupted streams
