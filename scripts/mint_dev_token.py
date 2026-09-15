"""Mint a dev JWT for local JWT-mode testing (REGINTEL_AUTH_MODE=jwt).

Dev-only convenience — uses the same REGINTEL_JWT_SECRET the API validates
against. Never for production; real tokens come from Entra ID.

Usage:
    REGINTEL_JWT_SECRET=devsecret .venv/bin/python scripts/mint_dev_token.py \
        --sub e001 --name "Asha Verma" --department IT --roles employee
"""

import argparse
import os
import time

import jwt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sub", default="e001")
    parser.add_argument("--name", default="Asha Verma")
    parser.add_argument("--department", default="IT")
    parser.add_argument("--roles", nargs="*", default=["employee"])
    parser.add_argument("--ttl", type=int, default=3600)
    parser.add_argument("--issuer", default=os.getenv("REGINTEL_JWT_ISSUER", "regintel-dev"))
    parser.add_argument("--audience", default=os.getenv("REGINTEL_JWT_AUDIENCE", "regintel-api"))
    args = parser.parse_args()

    secret = os.getenv("REGINTEL_JWT_SECRET")
    if not secret:
        raise SystemExit("REGINTEL_JWT_SECRET must be set (dev key only)")

    now = int(time.time())
    token = jwt.encode(
        {
            "sub": args.sub,
            "name": args.name,
            "department": args.department,
            "roles": args.roles,
            "iss": args.issuer,
            "aud": args.audience,
            "iat": now,
            "exp": now + args.ttl,
        },
        secret,
        algorithm="HS256",
    )
    print(token)


if __name__ == "__main__":
    main()
