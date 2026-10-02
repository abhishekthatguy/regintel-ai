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
| **UI (Streamlit)** | **`https://regintel-ai-test.streamlit.app`** — the demo link |

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

## 2. Deploy the UI on Streamlit Cloud (~3 min) — DONE

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
  is the demo identity — no password, no bearer token needed. Real JWT
  mode is documented below — it stays **off** on the demo instance so
  evaluators can click through without a token.
- **Free-tier redeploys**: push to `master` on GitHub → Render
  auto-deploys the new commit (or use the deploy hook). Streamlit Cloud
  picks up pushes automatically too.
- **Angular stays local** (`ui/web`) — Streamlit covers the demo surface.
  To deploy it later: build `dist/` against the API URL and host as a
  Render static site; set `REGINTEL_ALLOWED_ORIGINS` on the API to the
  static site domain (browser CORS).

## 4. JWT auth mode (production path)

The demo instance runs `REGINTEL_AUTH_MODE=stub` so evaluators need no
credentials. The deployed API supports real JWT auth — verified: 401 on
missing/forged tokens, 200 with a valid token, `/health` stays public.

To switch Render to JWT mode:

1. Render → `regintel-api` → **Environment** → add:
   ```
   REGINTEL_AUTH_MODE=jwt
   REGINTEL_JWT_SECRET=<random 64-char secret>
   ```
   (optional: `REGINTEL_JWT_ISSUER` / `REGINTEL_JWT_AUDIENCE` /
   `REGINTEL_JWT_JWKS_URL` for an external IdP such as Entra ID — JWKS
   mode needs no shared secret)
2. Save → Render redeploys.
3. **Evaluator token flow** — mint a long-lived demo token locally:
   ```bash
   REGINTEL_JWT_SECRET=<same-secret> .venv/bin/python scripts/mint_dev_token.py \
       --sub e001 --name "Asha Verma" --department IT --roles employee --ttl 86400
   ```
4. In the Streamlit sidebar, paste the token into **Bearer token** —
   every request then carries `Authorization: Bearer <token>`; the
   employee dropdown no longer controls identity (`sub` is authoritative).
   For an unattended demo, set it as a Streamlit secret the app reads.
5. Flip back to `stub` for friction-free evaluation.

Trade-off: JWT mode blocks click-through demos (every user needs a
token), so the submitted instance intentionally stays on `stub` while
the JWT path remains one env-var flip away.

## 5. Supabase Auth (real signup/signin — production path)

`REGINTEL_AUTH_MODE=supabase` swaps stub auth for a real account system —
email/password signup + signin + forgot-password, all proxied through
`/v1/auth/*` so Supabase keys never reach the browser.

Setup on a dedicated Supabase project:

1. Create the project (dashboard → New project). Grab URL + keys from
   **Settings → API Keys** (publishable + secret — not the legacy
   anon/service_role unless required).
2. Run `db/supabase_profiles.sql` in the project SQL editor — creates
   `public.profiles` with RLS (users read their own row; writes are
   server-only).
3. Set env vars (local `.env` / Render dashboard):
   ```
   REGINTEL_AUTH_MODE=supabase
   REGINTEL_SUPABASE_URL=https://<ref>.supabase.co
   REGINTEL_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
   REGINTEL_SUPABASE_SECRET_KEY=sb_secret_...
   ```
4. Bootstrap the first admin link (assigning requires an approved admin):
   ```bash
   # sign up via the UI first, then grab the user's UUID from
   # Supabase dashboard → Authentication → Users
   REGINTEL_SUPABASE_URL=... REGINTEL_SUPABASE_SECRET_KEY=... \
     .venv/bin/python scripts/supabase_link_user.py <auth-user-uuid> e999
   ```
   After that, admins link accounts via `GET /v1/auth/pending-users` +
   `POST /v1/auth/assign-employee`.

How it works: signup creates the auth account + a **pending** profile —
it can't do anything until an admin assigns an employee (department +
roles copied from the employees table, never from user-editable fields).
Requests verify the Supabase JWT via JWKS
(`/auth/v1/.well-known/jwks.json`), falling back to `GET /auth/v1/user`
for HS256-signed projects. The Streamlit sidebar shows a sign-in form
automatically when the API reports `auth_mode=supabase`.

Email delivery for confirm/reset links uses Supabase's built-in SMTP on
the free tier (rate-limited — fine for demo; configure custom SMTP for
production).

## 6. Cloud backends (production path)

Local defaults are SQLite + in-process TTL cache. The production
adapters are real and config-selected:

| Setting | Value | Effect |
|---|---|---|
| `REGINTEL_STORE_BACKEND` | `dynamodb` | `DynamoDBStore` (boto3) replaces `SQLiteStore` — conversations/tickets/KB/app tables, auto-created by `init_schema`. Needs `AWS_REGION` + AWS credentials (`AWS_PROFILE` locally, IAM role on the host in prod). |
| `REGINTEL_CACHE_BACKEND` | `redis` | `RedisCache` (redis-py) replaces `LocalTTLCache` for retrieval responses. Needs `REGINTEL_REDIS_URL` (ElastiCache / Upstash / Render Key Value). Connection failure degrades to local TTL — never breaks requests. |
| `REGINTEL_LLM_PROVIDER` | `hf` / `bedrock` | HF Inference Providers (`REGINTEL_HF_TOKEN`) or Bedrock Converse (`AWS_REGION`); falls back to the deterministic local model when unconfigured. |
| `REGINTEL_EMBEDDER` | `hf` | Semantic embeddings via `sentence-transformers/all-MiniLM-L6-v2` (384-dim). |

All backends are exercised in CI without real services: `fakeredis` for
the cache, `moto` for DynamoDB, mocked-HTTP for HF. On Render's free tier
the SQLite fallback is deliberate — free Postgres/Redis exist but the
ephemeral filesystem note above explains the demo data model.

## What the evaluator sees

- Full chat flow — citations, not-found honesty, ticket create with
  confirm+dedupe, CRM lookup — everything in `docs/demo-script.md`
  works over the public link.
- Admin/Eval pages: Eval hits the live API; Admin shows use-case config
  + corpus tabs (data tab needs the API-side DB).
- API docs are public too: `/openapi.json`, `/health`, `/ready`.
