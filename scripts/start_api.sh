#!/usr/bin/env bash
# Start the RegIntel API for hosted deploys (Render, Railway, a VM, ...).
# Seeds the demo DB first so a fresh container demos immediately;
# the knowledge corpus auto-ingests on first request.
set -euo pipefail
PY="$(command -v python3 || command -v python)"
"$PY" scripts/seed_db.py
exec "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
