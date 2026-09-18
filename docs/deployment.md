# Live demo deployment — free tier, no cloud account plumbing

Two free services, both deploy straight from the GitHub repo:

- **API** → Render (free web service)
- **UI** → Streamlit Community Cloud (free)

The Streamlit app already speaks HTTP to the API via `REGINTEL_API_BASE`,
so no code changes are needed — just config.

## 1. Deploy the API on Render (~5 min)

1. https://render.com → sign in with GitHub.
2. **New → Blueprint** → select `abhishekthatguy/regintel-ai`.
   `render.yaml` in the repo defines the service automatically:
   build `pip install -e .`, start `bash scripts/start_api.sh`,
   health check `/health`, plan `free`.
3. Apply → wait for deploy (~3–5 min). Render gives you a URL like
   `https://regintel-api.onrender.com`.
4. Verify: open `https://<your-url>.onrender.com/ready` →
   `{"ready":true,...}`.

> First request triggers corpus auto-ingestion (~seconds). The demo DB is
> seeded by `scripts/start_api.sh` — employees e001–e003/e999, tickets,
> CRM cases all present.

## 2. Deploy the UI on Streamlit Cloud (~3 min)

1. https://share.streamlit.io → sign in with GitHub.
2. **New app** → repo `abhishekthatguy/regintel-ai`, branch `master`,
   main file `ui/streamlit_app.py`.
3. **Advanced settings → Secrets**:
   ```toml
   REGINTEL_API_BASE = "https://<your-render-url>.onrender.com"
   ```
4. Deploy → you get `https://<app>.streamlit.app`.

## 3. Verify the live demo

Open the Streamlit URL → pick `e001` + IT Support → ask
*"how do I connect to the VPN"* → grounded answer with citation cards,
streamed live from the Render API. Eval page runs the golden suite
against the live API.

## What the evaluator sees

- Full chat flow (citations, not-found honesty, ticket create with
  confirm+dedupe, CRM lookup) — everything in `docs/demo-script.md`
  works over the public link.
- Admin/Eval pages: Eval hits the live API; Admin's data tab needs the
  API-side DB (shows config + corpus tabs regardless).

## Known constraints (free tier)

- **Render free spins down after ~15 min idle** — first request after
  idle takes ~30–60s (cold start). Hit `/health` once before demoing.
- **SQLite is ephemeral** — data resets on each redeploy; fine for a
  demo (seed script re-runs on start).
- Stub auth means the demo employee dropdown is the "login" — same as
  local. JWT mode works too if you set `REGINTEL_AUTH_MODE=jwt` +
  `REGINTEL_JWT_SECRET` on Render.
- Angular app stays local (`ui/web`) — Streamlit covers the demo
  surface. To deploy it later: build with the API URL and host the
  `dist/` output as a Render static site.
