"""Refresh the Hugging Face OAuth session token and update .env.local.

Devin's HF MCP OAuth credential (~/.local/share/devin/mcp/oauth/*.json)
holds a refresh token; each refresh mints a new ~8h access token with the
`inference-api` scope. HF does not allow API-token creation via OAuth, so
this keeps REGINTEL_HF_TOKEN current without a manual settings-page visit.

For a permanent token instead: https://huggingface.co/settings/tokens ->
"Create new token" -> enable "Make calls to Inference Providers".

Usage:
    .venv/bin/python scripts/hf_refresh_token.py            # refresh + write
    .venv/bin/python scripts/hf_refresh_token.py --check    # verify only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_LOCAL = PROJECT_ROOT / ".env.local"
OAUTH_DIR = Path.home() / ".local" / "share" / "devin" / "mcp" / "oauth"
TOKEN_URL = "https://huggingface.co/oauth/token"
WHOAMI_URL = "https://huggingface.co/api/whoami-v2"


def _find_hf_oauth() -> Path:
    for f in OAUTH_DIR.glob("*.json"):
        if json.loads(f.read_text()).get("server_name") == "huggingface":
            return f
    sys.exit(f"no huggingface oauth credential under {OAUTH_DIR}")


def _post(url: str, data: dict, token: str | None = None) -> tuple[int, dict]:
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read() or b"{}"
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"raw": raw[:200].decode(errors="replace")}


def _update_env(token: str) -> None:
    text = ENV_LOCAL.read_text()
    ENV_LOCAL.write_text(
        re.sub(r"^REGINTEL_HF_TOKEN=.*$", f"REGINTEL_HF_TOKEN={token}", text, flags=re.M)
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify current token only")
    args = ap.parse_args()

    cred_path = _find_hf_oauth()
    cred = json.loads(cred_path.read_text())

    if not args.check:
        status, r = _post(
            TOKEN_URL,
            {
                "grant_type": "refresh_token",
                "refresh_token": cred["refresh_token"],
                "client_id": cred["client_id"],
            },
        )
        if status != 200:
            sys.exit(f"refresh failed ({status}): {r}")
        cred["access_token"] = r["access_token"]
        cred["refresh_token"] = r.get("refresh_token", cred["refresh_token"])
        cred["expires_at"] = int(time.time()) + r.get("expires_in", 28800)
        cred_path.write_text(json.dumps(cred))
        _update_env(cred["access_token"])
        print("refreshed and written to .env.local")

    token = (
        cred["access_token"]
        if not args.check
        else next(
            (
                line.split("=", 1)[1].strip()
                for line in ENV_LOCAL.read_text().splitlines()
                if line.startswith("REGINTEL_HF_TOKEN=")
            ),
            "",
        )
    )
    _, who = _post(WHOAMI_URL, {}, token=token)
    exp = who.get("auth", {}).get("expiresAt", "?")
    print(f"whoami: {who.get('name')} | auth: {who.get('auth',{}).get('type')} | expires: {exp}")


if __name__ == "__main__":
    main()
