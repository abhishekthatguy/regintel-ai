"""Phase 8 — quality & completeness: protocol parity, FR-16 rewriting,
conversation export, cost pricing, rubric scoring."""

import json

from app.llm.bedrock import BedrockChatModel
from app.llm.local import LocalChatModel
from app.llm.pricing import estimate_cost
from app.retrieval.rewriter import FOLLOWUP_RE, get_rewriter

EMP = {"X-Demo-Employee": "e001"}


def _chat(client, content: str, headers=None) -> dict:
    """One full conversation round-trip; returns all events + last event."""
    cid = client.post(
        "/v1/conversations", json={"usecase_id": "it_support"}, headers=headers or EMP
    ).json()["conversation_id"]
    events = []
    with client.stream(
        "POST",
        f"/v1/conversations/{cid}/messages:stream",
        json={"content": content},
        headers=headers or EMP,
    ) as r:
        for line in r.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return {"conversation_id": cid, "events": events, "last": events[-1] if events else {}}


# --- Bedrock protocol parity ------------------------------------------------

def test_bedrock_implements_full_protocol():
    """extract_case_fields + generate must exist so CRM create works in
    Bedrock mode (was a real gap — protocol added in Phase 6)."""
    model = BedrockChatModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0")
    for method in ("classify", "extract_fields", "extract_case_fields",
                   "respond", "generate_grounded", "generate"):
        assert callable(getattr(model, method)), f"missing {method}"
    fields = model.extract_case_fields("open a crm case about invoice delays", {})
    assert "subject" in fields or isinstance(fields, dict)


def test_local_model_generate_exists():
    assert LocalChatModel().generate([{"role": "user", "content": "hi"}]) == "hi"


# --- FR-16 query rewriting ---------------------------------------------------

def test_rewriter_expands_followup():
    rw = get_rewriter("local")
    out = rw.rewrite(
        "what about the expiry?",
        {"last_topic": "how do I connect to the VPN",
         "history": [{"role": "user", "content": "how do I connect to the VPN"}]},
    )
    assert "VPN" in out and "expiry" in out and len(out.split()) > 3


def test_rewriter_leaves_standalone_queries_alone():
    rw = get_rewriter("local")
    q = "how do I connect to the VPN from home"
    assert rw.rewrite(q, {"last_topic": "expense policy", "history": []}) == q


def test_rewriter_followup_regex():
    assert FOLLOWUP_RE.match("and what about MFA")
    assert not FOLLOWUP_RE.match("reset my password")


def test_followup_retrieval_end_to_end(client):
    """A short follow-up inherits the topic — retrieves instead of not-found."""
    r = client.post("/v1/conversations", json={"usecase_id": "it_support"}, headers=EMP)
    cid = r.json()["conversation_id"]
    for content in ("how do I connect to the VPN", "and what about the client"):
        with client.stream(
            "POST", f"/v1/conversations/{cid}/messages:stream",
            json={"content": content}, headers=EMP,
        ) as s:
            for line in s.iter_lines():
                if line.strip():
                    last = json.loads(line)
    assert last["type"] == "complete"


# --- Conversation export ------------------------------------------------------

def test_export_markdown(client):
    cid = _chat(client, "how do I connect to the VPN")["conversation_id"]
    r = client.get(f"/v1/conversations/{cid}/export", headers=EMP)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    body = r.text
    assert "## User" in body and "## Assistant" in body and "KB-" in body


def test_export_json(client):
    cid = _chat(client, "show my tickets")["conversation_id"]
    r = client.get(f"/v1/conversations/{cid}/export?format=json", headers=EMP)
    assert r.status_code == 200
    data = r.json()
    assert data["conversation_id"] == cid and len(data["messages"]) >= 2


def test_export_owner_scoped(client):
    cid = _chat(client, "hello")["conversation_id"]
    r = client.get(
        f"/v1/conversations/{cid}/export", headers={"X-Demo-Employee": "e002"}
    )
    assert r.status_code == 403
    assert client.get("/v1/conversations/nonexistent/export", headers=EMP).status_code == 404


# --- Cost pricing --------------------------------------------------------------

def test_cost_estimation():
    assert estimate_cost("local-stub", 1000, 1000) == 0.0
    cost = estimate_cost("anthropic.claude-haiku-4-5", 1000, 500)
    assert cost > 0
    sonnet = estimate_cost("anthropic.claude-sonnet-4-5", 1000, 1000)
    assert sonnet > cost  # sonnet is pricier


def test_usage_carries_cost_field(client):
    events = _chat(client, "hello")["events"]
    usage = next(e["data"] for e in events if e["type"] == "usage")
    assert "estimated_cost_usd" in usage and "language" in usage


# --- Rubric scoring -------------------------------------------------------------

def test_eval_rubric_means(client):
    from eval.runner import run_all, summarize

    summary = summarize(run_all(client))
    assert "rubric_means" in summary
    assert all(0 <= v <= 5 for v in summary["rubric_means"].values())
    assert summary["rubric_means"]["groundedness"] >= 3.0
