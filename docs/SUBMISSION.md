# Submission Package — IIT Patna GenAI Program, Project 3

Maps every requirement in `docs/IITPatna-USDC-GenAI-Development-Program-Final-Evaluation (1).docx`
to where it lives in this repo. Everything below is verified locally.

## Requirement → artifact

### 1. Source code

- Complete Python source under `app/`, `eval/`, `scripts/`, `ui/`.
- Modular layout: `app/agent` (LangGraph), `app/tools`, `app/retrieval`,
  `app/ingestion`, `app/llm`, `app/identity`, `app/crm`, `app/stores`,
  `app/api`, `app/schemas`, `app/guardrails`, `app/integrations`.
- No hard-coded secrets; all config via env vars (`.env.example`).

### 2. README.md contents

| Required | Where |
|---|---|
| Project title / problem / overview | `README.md` — title, Problem, Solution |
| Architecture diagram | `README.md` → Architecture; detail in `docs/architecture.md` |
| Technology stack | `README.md` → Technology stack |
| Project structure | `README.md` → Layout |
| Setup instructions | `README.md` → Setup / Run |
| Environment variables | `README.md` → Environment variables; `.env.example` |
| How to run | `README.md` → Run (API + Streamlit + Angular) |
| Sample inputs / outputs | `README.md` → Sample inputs & outputs; `docs/demo-script.md` |
| Key design decisions | `README.md` → Design decisions; `docs/decisions-and-open-questions.md` |
| Limitations | `README.md` → Notes / limitations |

### 3. Sample data

- Knowledge corpus: `data/knowledge/` — 28+ markdown docs across IT, HR,
  Finance, Security, Facilities (mixed ACLs for access-control demos).
- Tickets, employees, CRM cases: `data/seed/`.
- Use-case configs: `data/usecases/*.yaml`.
- Evaluator needs nothing else — `scripts/seed_db.py` + auto-ingestion
  bootstrap everything.

### 4. Demonstration

- Live walkthrough: `docs/demo-script.md` — 11 steps, exact prompts,
  expected outputs.
- For a recorded video: follow the script top-to-bottom (~8 min); narration
  notes are inline. Recommended order: grounded answer → not-found →
  ticket create (confirm+dedupe) → CRM lookup (scope) → finance dept →
  voice → analytics → eval suite.
- Pitch deck: `docs/submission/RegIntel-AI-Pitch-Deck.pptx`
  (source: `docs/pitch-deck.md`; regenerate via `scripts/build_pitch_deck.py`).

### 5. GitHub repository checklist

- [x] Source code, `README.md`, sample data, `pyproject.toml`, `.env.example`
- [x] Architecture diagram (README + `docs/architecture.md`)
- [x] No secrets committed — `.env` is gitignored; verify before push:
      `git grep -n "secret\|api.key\|password" -- '*.py' '*.yaml' '*.env*'`
      should only show placeholders/examples.
- [x] CI green: `.github/workflows/ci.yml` (ruff + pytest + Angular build)

## Project 3 functional requirements → evidence

| Requirement | Evidence |
|---|---|
| ≥3 tools | 5 tools — `app/tools/` (knowledge, ticket lookup/create, CRM lookup/create) |
| Intent → tool → response | `app/agent/graph.py` — classify node + conditional routing |
| LangGraph (state, nodes, edges, routing) | `app/agent/graph.py`, `app/agent/runner.py` |
| Multi-turn memory | SQLite checkpointer; pending actions; FR-16 rewriting |
| Validation, dedupe, no hallucination | confirm/cancel flows, idempotent writes, rerank not-found |
| Streamlit UI | `ui/streamlit_app.py` (+ Angular `ui/web/`) |
| Error handling | `error_handler` node; guarded tool calls; graceful fallbacks |
| Modular, Python, local | `pip install -e .` then two commands; no paid services needed |

## Verification snapshot

- `pytest`: **103 passed** — unit, integration, security, 31-case golden eval
- `ruff check .`: clean
- `cd ui/web && npm run build`: clean
- Perf: P95 first-token ≈65 ms, answer ≈70 ms (`scripts/load_test.py`)

## How to submit

1. Push this repo to GitHub (run the secrets grep first).
2. Record the demo video following `docs/demo-script.md` (or demo live).
3. Include the pitch deck `docs/submission/RegIntel-AI-Pitch-Deck.pptx`.
4. Point evaluators at `README.md` → `docs/` → this file.
