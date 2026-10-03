# Evaluator Demo Script — RegIntel AI

A repeatable walkthrough for the IIT Patna Project 3 evaluation and pilot
readiness review. Everything runs locally; no credentials needed.

Two model modes, same flow: **local deterministic** (default, offline,
fully reproducible) or **Hugging Face** (`REGINTEL_LLM_PROVIDER=hf` +
`REGINTEL_HF_TOKEN` + `REGINTEL_EMBEDDER=hf` in `.env.local` — real
Llama-3.1-8B grounded answers and MiniLM semantic retrieval; provider
failure falls back to local automatically). Delete `data/regintel.db` and
restart the API after switching embedders so chunks re-ingest in the new
vector space.

## Setup (one time)

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python scripts/seed_db.py
```

## Run

```bash
.venv/bin/uvicorn app.main:app --port 8000        # API
.venv/bin/streamlit run ui/streamlit_app.py       # Streamlit UI :8501
cd ui/web && npx ng serve                         # Angular UI :4200
```

## Walkthrough (Angular :4200 or Streamlit :8501)

0. **Capability greeting** — *"how can you help me"* → deterministic
   capability answer (never goes to retrieval).
1. **Knowledge answer with citations** — e001 / IT Support:
   *"how do I connect to the VPN"* → grounded answer, expandable citation
   cards (document, section, scores, version, source URL). In HF mode,
   also try the paraphrase *"what is the vacation policy"* → retrieves
   Leave and Time-Off Policy semantically.
2. **Not-found honesty** — *"what is the cafeteria menu"* → explicit
   "couldn't find evidence" — no guessing; recorded for the analytics gap view.
3. **Ticket lookup** — *"show my tickets"* → own tickets only.
4. **Ticket create + confirm + dedupe** — *"create a ticket my laptop battery
   drains in an hour"* → confirm prompt → `yes` → TCK created. Repeat →
   duplicate reused, not re-created. `no` / `no thanks` cancels
   conversationally — nothing written, context kept, and *"create a
   ticket"* again resumes with remembered fields.
5. **CRM read/write** — *"check my case CASE-7001"*; *"open a crm case about
   delayed vendor invoices"* → same clarify → confirm → idempotent write → audit.
6. **Voice** — 🎤 dictate a question (transcript preserved as the message);
   🔊 reads the answer aloud.
7. **Access control** — switch to e002/HR (the sidebar auto-starts a fresh
   session on employee/use-case change), ask *"what is the budget process"* →
   Finance-restricted docs never cited (server-side ACL on both retrieval legs).
   HR use case also refuses ticket/CRM tools by config.
8. **Third department** — e003/Finance use case → Finance corpus + CRM, all
   config-only (UJ-07).
9. **Genesys agent-assist** — `curl POST /v1/integrations/genesys/suggest`
   with an utterance → suggestion + citations (stateless).
10. **Analytics** — `/analytics` as e999: adoption funnel, cost by department,
    unmet-need clusters, feedback.
11. **Admin self-service** — `GET /v1/admin/usecases`, `POST /v1/admin/knowledge`
    (upload a doc → instantly retrievable), ingestion jobs.

## Auth modes (sidebar auto-detects via `/health`)

| `REGINTEL_AUTH_MODE` | What the evaluator sees |
|---|---|
| `stub` (default/demo) | Employee dropdown — pick e001–e003/e999, no credentials |
| `jwt` | Bearer-token field — mint with `scripts/mint_dev_token.py` |
| `supabase` | Real sign-in/sign-up/forgot-password tabs; new accounts stay pending until an admin links an employee |

Manual end-to-end matrix per use case: `docs/e2e-test-checklist.md`.

## Verification commands

```bash
.venv/bin/pytest                 # full suite (incl. 31-case golden eval)
.venv/bin/ruff check .
cd ui/web && npm run build
.venv/bin/python scripts/load_test.py   # P95 vs NFR latency targets
.venv/bin/python scripts/export_openapi.py > regintel.openapi.json
```
