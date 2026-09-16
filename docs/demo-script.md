# Evaluator Demo Script — RegIntel AI

A repeatable walkthrough for the IIT Patna Project 3 evaluation and pilot
readiness review. Everything runs locally; no credentials needed.

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

1. **Knowledge answer with citations** — e001 / IT Support:
   *"how do I connect to the VPN"* → grounded answer, expandable citation
   cards (document, section, scores, version, source URL).
2. **Not-found honesty** — *"what is the cafeteria menu"* → explicit
   "couldn't find evidence" — no guessing; recorded for the analytics gap view.
3. **Ticket lookup** — *"show my tickets"* → own tickets only.
4. **Ticket create + confirm + dedupe** — *"create a ticket my laptop battery
   drains in an hour"* → confirm prompt → `yes` → TCK created. Repeat →
   duplicate reused, not re-created.
5. **CRM read/write** — *"check my case CASE-7001"*; *"open a crm case about
   delayed vendor invoices"* → same clarify → confirm → idempotent write → audit.
6. **Voice** — 🎤 dictate a question (transcript preserved as the message);
   🔊 reads the answer aloud.
7. **Access control** — switch to e002/HR, ask *"what is the budget process"* →
   Finance-restricted docs never cited (server-side ACL on both retrieval legs).
8. **Third department** — e003/Finance use case → Finance corpus + CRM, all
   config-only (UJ-07).
9. **Genesys agent-assist** — `curl POST /v1/integrations/genesys/suggest`
   with an utterance → suggestion + citations (stateless).
10. **Analytics** — `/analytics` as e999: adoption funnel, cost by department,
    unmet-need clusters, feedback.
11. **Admin self-service** — `GET /v1/admin/usecases`, `POST /v1/admin/knowledge`
    (upload a doc → instantly retrievable), ingestion jobs.

## Verification commands

```bash
.venv/bin/pytest                 # full suite (incl. 31-case golden eval)
.venv/bin/ruff check .
cd ui/web && npm run build
.venv/bin/python scripts/load_test.py   # P95 vs NFR latency targets
.venv/bin/python scripts/export_openapi.py > regintel.openapi.json
```
