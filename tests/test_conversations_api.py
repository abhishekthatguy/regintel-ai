import json


def create_conversation(client, usecase="it_support", employee="e001"):
    resp = client.post(
        "/v1/conversations",
        json={"usecase_id": usecase},
        headers={"X-Demo-Employee": employee},
    )
    assert resp.status_code == 201
    return resp.json()


def test_create_conversation(client):
    body = create_conversation(client)
    assert body["conversation_id"]
    assert body["usecase_id"] == "it_support"
    assert body["usecase_version"] == 1


def test_create_conversation_unknown_usecase(client):
    resp = client.post("/v1/conversations", json={"usecase_id": "nope"})
    assert resp.status_code == 404


def test_stream_message_emits_event_sequence(client):
    conv = create_conversation(client)
    with client.stream(
        "POST",
        f"/v1/conversations/{conv['conversation_id']}/messages:stream",
        json={"content": "how do I reset my password?"},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/x-ndjson")
        events = [json.loads(line) for line in resp.iter_lines() if line]

    types = [e["type"] for e in events]
    assert types[0] == "status"
    assert "token" in types
    assert "usage" in types
    assert types[-1] == "complete"

    answer = "".join(e["data"]["text"] for e in events if e["type"] == "token")
    assert answer  # grounded answer streamed


def test_messages_persisted_after_stream(client):
    conv = create_conversation(client)
    with client.stream(
        "POST",
        f"/v1/conversations/{conv['conversation_id']}/messages:stream",
        json={"content": "persist me"},
    ) as resp:
        list(resp.iter_lines())

    loaded = client.get(f"/v1/conversations/{conv['conversation_id']}").json()
    assert [m["role"] for m in loaded["messages"]] == ["user", "assistant"]
    assert loaded["messages"][0]["content"] == "persist me"
    assert loaded["messages"][0]["correlation_id"]
    assert loaded["messages"][1]["usage"]["total_tokens"] > 0


def test_get_conversation_forbidden_for_other_user(client):
    conv = create_conversation(client, employee="e001")
    resp = client.get(
        f"/v1/conversations/{conv['conversation_id']}",
        headers={"X-Demo-Employee": "e002"},
    )
    assert resp.status_code == 403


def test_get_conversation_not_found(client):
    assert client.get("/v1/conversations/nope").status_code == 404


def test_stream_unknown_conversation(client):
    resp = client.post("/v1/conversations/nope/messages:stream", json={"content": "hi"})
    assert resp.status_code == 404


def test_list_conversations_scoped(client):
    create_conversation(client, employee="e001")
    resp = client.get("/v1/conversations", headers={"X-Demo-Employee": "e001"})
    assert len(resp.json()) == 1
    resp = client.get("/v1/conversations", headers={"X-Demo-Employee": "e002"})
    assert len(resp.json()) == 0
