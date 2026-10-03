# Phase 9 — Production Readiness

**Goal**: answer the evaluator's production-readiness feedback head-on —
"complete the cloud integrations currently represented as adapter/skeleton
boundaries, replace demo/stub authentication in deployed environments, and
strengthen distributed persistence/cache beyond SQLite/local backends."

## Scope

| Item | Reviewer gap | Status |
|---|---|---|
| 9.1 Hugging Face provider | skeleton model boundaries → real LLM + embeddings | ✅ implemented + **connected live** |
| 9.2 Redis cache | `RedisCache` raised on use → real client | ✅ implemented |
| 9.3 DynamoDB store | `DynamoDBStore` raised on use → real boto3 impl | ✅ implemented |
| 9.4 Deployed auth | stub header → real Supabase Auth (signup/signin/forgot) + JWT mode | ✅ implemented — live Supabase project pending |
| 9.5 HF MCP server | agent tooling for HF Hub (spaces/models/datasets) | ✅ connected (OAuth) |

## Delivered

### 9.1 Hugging Face provider (`app/llm/hf.py`, `app/retrieval/embeddings.py`)

- `HFChatModel` — full `ChatModel` contract over HF Inference Providers'
  OpenAI-compatible chat-completions API (`REGINTEL_LLM_PROVIDER=hf`,
  `REGINTEL_HF_TOKEN`, `REGINTEL_HF_MODEL` — Llama-3.1-8B default). The LLM
  does classification, field extraction and grounded answer composition;
  write confirmations/clarify/refusals stay template-deterministic. Every
  method degrades to `LocalChatModel` without a token or on API errors.
- `HFEmbedder` — `sentence-transformers/all-MiniLM-L6-v2` via the HF
  feature-extraction API (`REGINTEL_EMBEDDER=hf`): real 384-dim semantic
  vectors, so paraphrases/synonyms retrieve correctly instead of relying
  on BM25 alone.
- `generate_grounded` gained `offer` + `question` params across local, HF
  and Bedrock implementations.
- Provider/embedder selection reads pydantic settings → `.env` works.

### 9.2 Real Redis cache (`app/cache.py`)

`RedisCache` is now a real `redis-py` client — `get`/`set`/`invalidate`
with TTL and prefix invalidation via `SCAN`. `get_cache()` selects on
`REGINTEL_CACHE_BACKEND=redis` + `REGINTEL_REDIS_URL`. Missing client or
connection failure degrades to `LocalTTLCache` — never crashes. Tested
with `fakeredis` (no server needed in CI).

### 9.3 Real DynamoDB store (`app/stores/dynamodb.py`)

`DynamoDBStore` is now a full boto3 implementation mirroring the
`SQLiteStore` surface — conversations, messages, tickets, CRM cases,
chunks + vectors, feedback, usage events, audit, ingestion jobs,
employees — behind the documented key schema:

- `CONV` table: `pk=CONV#{conversation_id}`, `sk=META | MSG#{created_at}#{id}`
- `TICKETS` table: `pk=EMP#{employee_id}`, `sk=TICKET#{id} | CASE#{id}`
- `KB` table: `pk=DOC#{doc_id}`, `sk=CHUNK#{chunk_id} | META`
- `APP` table: `pk=FEEDBACK|AUDIT|JOB|EMP#…`, time-ordered sort keys

Enabled via `REGINTEL_STORE_BACKEND=dynamodb` + table prefix env; tested
end-to-end against `moto` mocked DynamoDB (no AWS account needed).

### 9.4 Real backend auth (Supabase + JWT modes)

Two real authentication paths, both config-selected:

- **`REGINTEL_AUTH_MODE=supabase`** — full account system: email/password
  signup, signin, forgot-password, signout through `/v1/auth/*` (Supabase
  keys stay server-side). Identity = Supabase JWT verified via JWKS,
  mapped to an employee through `public.profiles` under an
  **admin-assigns** model — signup alone grants nothing; an admin links
  the account to an employee record (roles/department copied from the
  employees table, never user-editable claims). Bootstrap via
  `scripts/supabase_link_user.py`. Streamlit sidebar auto-switches to a
  sign-in form.
- **`REGINTEL_AUTH_MODE=jwt`** — HS256 dev tokens or Entra JWKS; mint a
  long-lived evaluator token with `scripts/mint_dev_token.py --sub e999`
  (deployment doc runbook).

### 9.5 HF MCP server (`.devin/mcp_config.json`)

HF's official MCP endpoint (`https://huggingface.co/mcp`) added at
project scope — OAuth via `devin mcp login huggingface`. Agent tooling
for model/space/dataset lookup during development; not part of the
runtime.

## Live verification (2026-10-03)

HF provider connected end-to-end on the local instance:

- `Settings` now loads `.env.local` after `.env` — gitignored local
  secrets (`REGINTEL_HF_TOKEN`) are honoured without touching `.env`.
- Permanent HF API token configured (Inference Providers scope);
  `whoami`/`chat.completions`/feature-extraction all verified 200.
- Corpus re-ingested with real 384-dim MiniLM embeddings (93 chunks);
  paraphrase queries ("vacation policy" → Leave and Time-Off Policy)
  retrieve semantically, and answers are LLM-composed grounded prose.
- Greeting/capability intents ("how can you help me", "what can you do")
  are deterministic on the HF path — classified locally before the LLM
  call so they can never flip to knowledge retrieval.
- `scripts/hf_refresh_token.py` kept as an OAuth-token fallback helper;
  not needed while the permanent API token is set.

## Still pending (operator actions)

- **Supabase secret key** — `profiles` table + RLS migrated on project
  `qqaaudputjojpglkpbzj`; GoTrue signup/signin/token verified with the
  publishable key, ES256 JWKS served. The only remaining step is pasting
  `REGINTEL_SUPABASE_SECRET_KEY` (dashboard → Settings → API Keys) and
  enabling `REGINTEL_AUTH_MODE=supabase` — profile writes are the only
  ops that need the secret key.
- **Real AWS credentials** — DynamoDB Local is live via
  `REGINTEL_DYNAMO_ENDPOINT`; swap `AWS_REGION` + real creds to go
  cloud. Same for `REGINTEL_LLM_PROVIDER=bedrock`.
- **Managed Redis** — local redis-server is live; point
  `REGINTEL_REDIS_URL` at ElastiCache/Upstash/Render KV for prod.
- **Enterprise integrations** — Genesys Cloud OAuth client + OpenText
  source adapter are boundaries pending org access (OQ-01/OQ-02).

## Verification

`pytest` — includes `test_hf_provider.py` (13 mocked-HTTP cases),
`test_cache.py` (fakeredis), `test_dynamodb_store.py` (moto). CI runs all
of them — no external services required.
