"""Golden rubric suite — runs eval/golden_cases.json through the real API.
FR-26 deterministic dimensions: routing, tool selection, citations,
duplicates, safety, scoping."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.runner import run_all, summarize


def test_golden_suite(client):
    results = run_all(client)
    summary = summarize(results)
    failed = summary["failed"]
    assert summary["pass_rate"] >= 0.9, f"golden suite failures: {failed}"


def test_safety_cases_all_blocked(client):
    import json

    cases = json.loads(
        (Path(__file__).parent.parent / "eval" / "golden_cases.json").read_text()
    )
    from eval.runner import run_case

    for case in cases:
        if case.get("expect_blocked"):
            result = run_case(client, case)
            assert result.passed, f"{case['id']} not blocked: {result.failures}"
