"""Local perf harness — measures stream latencies against NFR targets
(first token ≤4s P95, full answer ≤12s P95). Run against a live API:

    .venv/bin/python scripts/load_test.py [--requests 20] [--base http://localhost:8000]
"""

import argparse
import asyncio
import json
import statistics
import time

import httpx

QUERIES = [
    "how do I connect to the VPN",
    "what is the password reset policy",
    "show my tickets",
    "check my case CASE-7001",
    "how many vacation days do I get",
    "explain the corporate card policy",
    "what is the wifi setup process",
    "how do I report a phishing email",
]


async def measure(base: str, headers: dict) -> dict:
    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=60) as c:
        r = await c.post("/v1/conversations", json={"usecase_id": "it_support"})
        cid = r.json()["conversation_id"]
        q = QUERIES[hash(cid) % len(QUERIES)]
        t0 = time.perf_counter()
        first_token_at = answer_at = None
        async with c.stream(
            "POST", f"/v1/conversations/{cid}/messages:stream", json={"content": q}
        ) as resp:
            async for line in resp.aiter_lines():
                if not line:
                    continue
                ev = json.loads(line)
                if ev["type"] == "token" and first_token_at is None:
                    first_token_at = time.perf_counter() - t0
                if ev["type"] == "complete":
                    answer_at = time.perf_counter() - t0
        return {"first_token_s": first_token_at, "answer_s": answer_at, "ok": answer_at is not None}


def p95(xs: list[float]) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * 0.95))]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--requests", type=int, default=20)
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--employee", default="e001")
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args()

    headers = {"X-Demo-Employee": args.employee}
    sem = asyncio.Semaphore(args.concurrency)

    async def run_one():
        async with sem:
            return await measure(args.base, headers)

    results = await asyncio.gather(*(run_one() for _ in range(args.requests)))
    ok = [r for r in results if r["ok"] and r["first_token_s"]]
    print(f"\n{len(ok)}/{args.requests} streams completed")
    for label, key, target in (("first token", "first_token_s", 4.0), ("full answer", "answer_s", 12.0)):
        xs = [r[key] for r in ok]
        print(
            f"{label:12s} p50={statistics.median(xs):.3f}s  p95={p95(xs):.3f}s  "
            f"max={max(xs):.3f}s  target<={target}s  {'PASS' if p95(xs) <= target else 'FAIL'}"
        )


if __name__ == "__main__":
    asyncio.run(main())
