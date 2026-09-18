# Live demo deployment — free tier, no cloud plumbing

Two free services, both deploy straight from the GitHub repo:

- **API** → Render (free web service)
- **UI** → Streamlit Community Cloud (free) ← *the demo link to submit*

The Streamlit app already speaks HTTP to the API via `REGINTEL_API_BASE`,
so no code changes are needed — just config.

## Deployed instance (this project)

| Piece | URL |
|---|---|
| API (Render) | `https://regintel-api-xuhl.onrender.com` |
| Health / readiness | `https://regintel-api-xuhl.onrender.com/health` · `/ready` |
| OpenAPI spec | `https://regintel-api-xuhl.onrender.com/openapi.json` |
| Blueprint sync | Render dashboard → `regintel-api` service |
| **UI (Streamlit)** | `https://<app>.streamlit.app` — set after step 2 |

## 1. Deploy the API on Render (~5 min) — DONE

`render.yaml` in the repo is a Blueprint:

1. https://render.com → sign in with GitHub.
2. **New → Blueprint** → select `abhishekthatguy/regintel-ai` → **Apply**.
3. Render builds (`pip install -e .`), starts `bash scripts/start_api.sh`,
   health-checks `/health`, plan `free`.
4. Verify: `https://<url>.onrender.com/ready` → `{"ready":true,...}`.

`scripts/start_api.sh` seeds the demo DB (employees, tickets, CRM cases)
on every boot; the knowledge corpus auto-ingests on first agent request.

### Verified live (2026-09-18)

9/9 remote checks pass on the deployed API: auto-ingested citations
(KB-IT-001/009/006), not-found honesty, seeded ticket/CRM lookups,
create→confirm→TCK-1004, admin analytics 200/403 split, Genesys suggest,
conversation export.

## 2. Deploy the UI on Streamlit Cloud (~3 min)

1. https://share.streamlit.io → sign in with GitHub.
2. **New app** → repo `abhishekthatguy/regintel-ai`, branch `master`,
   main file `ui/streamlit_app.py`.
3. **Advanced settings → Secrets** — paste exactly:

   ```toml
   REGINTEL_API_BASE = "https://regintel-api-xuhl.onrender.com"
   ```

4. Deploy → you get `https://<app>.streamlit.app`.

## 3. Verify the live demo

Open the Streamlit URL → pick `e001` + IT Support → ask
*"how do I connect to the VPN"* → grounded answer with citation cards,
streamed from the Render API. The Eval page runs the golden suite
against the live API.

## ⚠️ Important operational notes

- **Cold starts (biggest demo risk)**: Render free tier **sleeps after
  ~15 min idle**. The first request after idle takes **30–60s** —
  everything still works, it just looks slow. **Before any demo or
  evaluation, warm it**: open `https://regintel-api-xuhl.onrender.com/health`
  ~1 min ahead, then the app is instant.
- **Deploy hook is a secret**: the Render deploy-hook URL
  (`https://api.render.com/deploy/srv-...?key=...`) triggers redeploys
  for anyone who has it. Keep it out of the repo/public places; rotate
  it in Render → Settings → Deploy Hook if it leaks.
- **SQLite is ephemeral**: the demo DB resets on every redeploy — the
  seed script re-runs on start, so demo data always comes back. Don't
  treat created tickets/cases as permanent.
- **Stub auth is the "login"**: the employee dropdown (e001–e003, e999)
  is the demo identity — no password, no bearer token needed. To demo
  real JWT: set `REGINTEL_AUTH_MODE=jwt` + `REGINTEL_JWT_SECRET` on
  Render, mint a token with `scripts/mint_dev_token.py --sub e999`,
  paste it in the sidebar token field.
- **Free-tier redeploys**: push to `master` on GitHub → Render
  auto-deploys the new commit (or use the deploy hook). Streamlit Cloud
  picks up pushes automatically too.
- **Angular stays local** (`ui/web`) — Streamlit covers the demo surface.
  To deploy it later: build `dist/` against the API URL and host as a
  Render static site; set `REGINTEL_ALLOWED_ORIGINS` on the API to the
  static site domain (browser CORS).

## What the evaluator sees

- Full chat flow — citations, not-found honesty, ticket create with
  confirm+dedupe, CRM lookup — everything in `docs/demo-script.md`
  works over the public link.
- Admin/Eval pages: Eval hits the live API; Admin shows use-case config
  + corpus tabs (data tab needs the API-side DB).
- API docs are public too: `/openapi.json`, `/health`, `/ready`.
