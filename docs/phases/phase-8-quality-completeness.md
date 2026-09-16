# Phase 8 — Quality & Completeness

**Goal**: close the last locally-deliverable gaps — Bedrock protocol parity,
FR-16 query rewriting, audit export, rubric scoring, real cost pricing, and
CI that runs the whole quality gate.

## Delivered

### Bedrock protocol parity
`BedrockChatModel` now implements the full `ChatModel` contract —
`extract_case_fields` (missing since the CRM write tool landed in Phase 6)
and `LocalChatModel.generate` (the freeform boundary `BedrockChatModel.generate`
falls back to). CRM case creation no longer crashes in Bedrock mode.
`test_bedrock_implements_full_protocol` guards every protocol method.

### FR-16 query rewriting / context enrichment
`app/retrieval/rewriter.py` — `QueryRewriter` protocol with two impls:

- `LocalQueryRewriter` — expands anaphoric/short follow-ups
  ("what about the expiry?") with `last_topic` + the previous user turn so
  retrieval stays grounded.
- `HaikuQueryRewriter` — real paraphrase through Bedrock when
  `models.enrichment` is configured to a cloud rewriter and the model is
  available; falls back to local otherwise.

Wired into the `retrieve` node — replaces the inline regex expansion.

### Conversation export
`GET /v1/conversations/{id}/export?format=markdown|json` — owner-scoped
transcript with title, use case + version, messages, and full citation
blocks. `Content-Disposition: attachment`. Angular chat header has an
**export** button (fetch + blob so auth headers travel with the request —
a bare link would resolve as the default stub identity).

### Heuristic rubric scoring
`eval/runner.py` scores every golden case on 5 dims (0–5): routing,
groundedness, citation_quality, completeness, safety — deterministic proxies
for the judged dims until an LLM judge is configured. `summarize()` returns
`rubric_means` alongside pass_rate.

### Real cost pricing
`app/llm/pricing.py` — per-1K-token rates for the configured model IDs
(Sonnet 4.5, Haiku 4.5, Nova Pro). `UsageSummary.estimated_cost_usd` now
carries a real estimate when a priced model is configured; `local-stub`
honestly reports 0. Department cost analytics already consume this field.

### CI
`.github/workflows/ci.yml` — triggers on `master` (was `main`-only, so CI
never ran on this repo's branch); adds a `web` job (npm ci + ng build) next
to lint + the full pytest suite (which includes the 31-case golden eval).

## Files

- `app/llm/bedrock.py` — `extract_case_fields`
- `app/llm/local.py` — `generate` freeform boundary
- `app/llm/pricing.py` — model rate table + `estimate_cost`
- `app/retrieval/rewriter.py` — FR-16 boundary
- `app/agent/graph.py` — rewriter wiring, cost computation in `respond`
- `app/api/routes_conversations.py` — export endpoint
- `eval/runner.py` — per-case rubric + `rubric_means`
- `ui/web` — export button, clearer resume errors
- `tests/test_phase8.py` — 12 tests

## Verified

- `pytest`: **103 passed** (12 new)
- `ruff`: clean · `ng build`: clean
- Live: export returns markdown transcript with citations; e002 → 403
- Eval summary includes rubric means

## Remaining honest gaps

- Rubric dims are heuristics, not judge scores — real LLM-judge eval needs
  a configured provider.
- Pricing table is a static approximation; cloud mode should prefer
  Bedrock's returned usage metadata.
- FR-16's paraphrase quality is regex-grade locally — Haiku path exercises
  real rewriting once credentials exist.
