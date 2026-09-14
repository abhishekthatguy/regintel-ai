# Evaluation Framework

A **rubric** = criteria + standards for performance levels, describing what each level looks like. Our evaluator scores labeled test cases against the dimensions below; it is a generic framework, not a vendor product.

## Rubric dimensions & pass targets (BRD §15)

| Dimension | Metric / method | Pass target |
|---|---|---|
| Intent & routing | Exact match against labeled scenarios | ≥90% |
| Tool selection | Correct tool + valid arguments | ≥90% |
| Retrieval relevance | Human-rated relevant chunks in top 5 | ≥80% of cases |
| Groundedness | Claims supported by retrieved evidence | Avg ≥4/5 |
| Citation correctness | Citation resolves to supporting source location | ≥95% |
| Completeness | Answer covers required question elements | Avg ≥4/5 |
| Safety | Prompt-injection, data-leakage, unauthorized-tool tests | 100% blocked/contained |
| State/memory | Follow-up scenarios retain correct context | ≥90% |
| Duplicate prevention | Repeated creates don't create duplicates | 100% |
| Regression | Golden dataset comparison in CI | No critical regression |

## How the runner works

1. **Golden dataset** — versioned test cases: input utterance(s), expected intent/tool, expected evidence doc IDs, expected answer elements, expected refusal/confirmation behavior. Department owners supply evaluation questions (BRD dependency).
2. **Execution** — each case runs through the real graph (or a recorded trace for CI speed), capturing: routed path, tool calls + args, retrieved chunk IDs, final answer, citations.
3. **Scoring** —
   - *Deterministic*: routing, tool selection, citation resolution, duplicate prevention, safety block → exact-match checks.
   - *Judged*: groundedness, completeness, relevance → rubric-scored (LLM-as-judge with a fixed rubric prompt, or human rating for the approved eval set).
4. **Report** — per-dimension scores vs targets; failures attach traces. Output feeds the analytics dashboard and the demo script.

## CI gates

`pytest` (unit/integration/contract) → rubric regression suite → only then build artifact → Nexus IQ policy scan → publish to JFrog. A critical regression or safety failure blocks the artifact.

## Phased rollout of the evaluator

| Phase | Evaluator capability |
|---|---|
| P1 | Runner skeleton; routing/tool-selection/state/duplicate/safety cases on the 3 core tools; judged dims scored manually or via configured LLM |
| P2 | Retrieval relevance (top-5) + citation correctness + groundedness against the golden retrieval set |
| P3 | Security/adversarial suite: injection, cross-department leakage, unauthorized tool calls |
| P4+ | Regression suite runs in CI against every change; dashboard visualizes trends |
