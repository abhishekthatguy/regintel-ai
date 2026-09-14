"""Rubric evaluation runner (FR-26 v1): executes golden cases through the real
API + graph and scores routing, tool use, citations, duplicates, safety.

Deterministic dimensions only in Phase 1; judged dims (groundedness etc.)
arrive with a configured judge in Phase 2.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

CASES_PATH = Path(__file__).parent / "golden_cases.json"

NODE_TOOL_MAP = {
    "retrieve": "knowledge_search",
    "ticket_lookup": "ticket_lookup",
    "ticket_create": "ticket_create",
}


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    nodes_seen: list[str] = field(default_factory=list)
    final_answer: str = ""


def _send_turn(client, conversation_id: str, content: str, employee: str) -> dict:
    with client.stream(
        "POST",
        f"/v1/conversations/{conversation_id}/messages:stream",
        json={"content": content},
        headers={"X-Demo-Employee": employee},
    ) as resp:
        events = [json.loads(line) for line in resp.iter_lines() if line]
    nodes = [e["data"]["detail"] for e in events if e["type"] == "status" and e["data"]["stage"] == "node"]
    answer = "".join(e["data"]["text"] for e in events if e["type"] == "token")
    citations = [e["data"] for e in events if e["type"] == "citation"]
    return {"nodes": nodes, "answer": answer, "citations": citations}


def run_case(client, case: dict) -> CaseResult:
    employee = case.get("employee", "e001")
    usecase = case.get("usecase", "it_support")
    resp = client.post(
        "/v1/conversations", json={"usecase_id": usecase}, headers={"X-Demo-Employee": employee}
    )
    conv_id = resp.json()["conversation_id"]

    result = CaseResult(case_id=case["id"], passed=True)
    last: dict = {}
    all_nodes: list[str] = []
    for turn in case["turns"]:
        last = _send_turn(client, conv_id, turn, employee)
        all_nodes += last["nodes"]
    result.nodes_seen = all_nodes
    result.final_answer = last.get("answer", "")

    def fail(msg: str) -> None:
        result.passed = False
        result.failures.append(msg)

    if "expect_intent" in case:
        expected_nodes = {
            "knowledge_query": ["retrieve"],
            "ticket_lookup": ["ticket_lookup"],
            "ticket_create": ["clarify", "duplicate_check", "confirm_action", "ticket_create"],
            "direct": ["generate"],
        }.get(case["expect_intent"], [])
        if expected_nodes and not any(n in all_nodes for n in expected_nodes):
            fail(f"intent {case['expect_intent']}: none of {expected_nodes} in {all_nodes}")

    if "expect_tool" in case:
        expected_nodes = [k for k, v in NODE_TOOL_MAP.items() if v == case["expect_tool"]]
        if case["expect_tool"] == "ticket_create":
            expected_nodes += ["duplicate_check", "confirm_action"]
        if not any(n in all_nodes for n in expected_nodes):
            fail(f"tool {case['expect_tool']}: no matching node in {all_nodes}")

    if case.get("expect_citations") and not last.get("citations"):
        fail("expected citations, none emitted")

    for doc_id in case.get("expect_docs", []):
        if not any(c.get("document_id") == doc_id for c in last.get("citations", [])):
            fail(f"expected citation to {doc_id}")

    for text in case.get("expect_contains", []):
        if text not in result.final_answer:
            fail(f"answer missing '{text}'")

    if case.get("scope_check"):
        forbidden = case["scope_check"].replace("no ", "")
        if forbidden in result.final_answer:
            fail(f"scope violation: '{forbidden}' appeared for another user's ticket")

    if case.get("expect_clarify") and "clarify" not in all_nodes:
        fail("expected clarify node for missing fields")

    if case.get("expect_duplicate"):
        if case["expect_duplicate"] not in result.final_answer:
            fail(f"expected duplicate reuse of {case['expect_duplicate']}")
        if "duplicate_check" not in all_nodes:
            fail("duplicate_check node not traversed")

    if case.get("expect_cancelled") and "ticket_create" in all_nodes:
        fail("ticket was created despite cancellation")

    if case.get("expect_not_found"):
        if "Here's what I found" in result.final_answer:
            fail("expected not-found response, got grounded answer")
        not_found_wording = "evidence" in result.final_answer or "couldn't find" in result.final_answer
        if not not_found_wording:
            fail("expected explicit not-found wording")

    if case.get("expect_blocked"):
        if "can't help" not in result.final_answer:
            fail("expected refusal message")

    return result


def run_all(client) -> list[CaseResult]:
    cases = json.loads(CASES_PATH.read_text())
    return [run_case(client, c) for c in cases]


def summarize(results: list[CaseResult]) -> dict:
    total = len(results)
    passed = sum(r.passed for r in results)
    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "failed": [{"id": r.case_id, "failures": r.failures} for r in results if not r.passed],
    }
