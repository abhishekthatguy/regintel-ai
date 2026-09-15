"""Phase 4: analytics API, language selection, not-found tracking (FR-20/22/25)."""

import json


def _send(client, conv, content, headers, **extra):
    events = []
    with client.stream(
        "POST",
        f"/v1/conversations/{conv}/messages:stream",
        json={"content": content, **extra},
        headers=headers,
    ) as resp:
        for line in resp.iter_lines():
            if line:
                events.append(json.loads(line))
    return events


def _new_conv(client, headers, usecase="it_support"):
    return client.post(
        "/v1/conversations", json={"usecase_id": usecase}, headers=headers
    ).json()["conversation_id"]


# --- language selection (FR-22) -------------------------------------------


def test_language_param_recorded_in_usage(client):
    conv = _new_conv(client, {"X-Demo-Employee": "e001"})
    events = _send(client, conv, "how do I reset my password?", {"X-Demo-Employee": "e001"},
                   language="hi")
    usage = next(e for e in events if e["type"] == "usage")
    assert usage["data"]["language"] == "hi"
    answer = "".join(e["data"]["text"] for e in events if e["type"] == "token")
    assert "requested language: hi" in answer  # honest local-model disclosure


def test_default_language_is_english(client):
    conv = _new_conv(client, {"X-Demo-Employee": "e001"})
    events = _send(client, conv, "hello", {"X-Demo-Employee": "e001"})
    usage = next(e for e in events if e["type"] == "usage")
    assert usage["data"]["language"] == "en"


# --- not-found tracking (FR-25 knowledge-manager view) ---------------------


def test_not_found_queries_are_tracked(client, get_store):
    conv = _new_conv(client, {"X-Demo-Employee": "e001"})
    _send(client, conv, "what is the airspeed velocity of a swallow?",
          {"X-Demo-Employee": "e001"})
    records = get_store.analytics_not_found()
    assert any("airspeed" in r["query"] for r in records)
    assert records[0]["usecase"] == "it_support"


# --- analytics endpoint (FR-25) --------------------------------------------


def test_analytics_requires_admin(client, auth_headers):
    assert client.get("/v1/admin/analytics").status_code == 403
    r = client.get("/v1/admin/analytics", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    for key in ("summary", "by_usecase", "daily", "not_found_queries", "recent_feedback"):
        assert key in body


def test_analytics_aggregates_real_data(client, auth_headers):
    conv = _new_conv(client, {"X-Demo-Employee": "e001"})
    _send(client, conv, "how do I reset my password?", {"X-Demo-Employee": "e001"})
    r = client.get("/v1/admin/analytics", headers=auth_headers).json()
    assert r["summary"]["assistant_messages"] >= 1
    assert r["summary"]["conversations"] >= 1
    assert any(u["usecase_id"] == "it_support" for u in r["by_usecase"])


def test_feedback_flows_into_analytics(client, auth_headers):
    conv = _new_conv(client, {"X-Demo-Employee": "e001"})
    events = _send(client, conv, "hello", {"X-Demo-Employee": "e001"})
    msg_id = next(e["data"]["message_id"] for e in events if e["type"] == "complete")
    client.post(
        f"/v1/messages/{msg_id}/feedback",
        json={"rating": "up", "comment": "helpful"},
        headers={"X-Demo-Employee": "e001"},
    )
    r = client.get("/v1/admin/analytics", headers=auth_headers).json()
    assert r["summary"]["feedback_up"] >= 1
    assert any(f["comment"] == "helpful" for f in r["recent_feedback"])
