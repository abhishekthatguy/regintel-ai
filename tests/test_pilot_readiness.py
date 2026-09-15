"""Phase 6 pilot-readiness tests: CRM write safety checklist, advanced
analytics, department-owner self-service views."""


def _conv(client, headers, usecase):
    r = client.post("/v1/conversations", headers=headers, json={"usecase_id": usecase})
    assert r.status_code == 201
    return r.json()["conversation_id"]


def _send(client, headers, cid, msg):
    """Returns (raw_lines, joined_answer_text) — tokens may split mid-word,
    so assertions on content must use the joined text."""
    import json as _json

    lines, text = [], ""
    with client.stream(
        "POST", f"/v1/conversations/{cid}/messages:stream",
        headers=headers, json={"content": msg},
    ) as r:
        assert r.status_code == 200
        for line in r.iter_lines():
            if not line:
                continue
            lines.append(line)
            ev = _json.loads(line)
            if ev["type"] == "token":
                text += ev["data"]["text"]
    return lines, text


def _h(auth_headers, employee):
    h = dict(auth_headers)
    h["X-Demo-Employee"] = employee
    return h


def test_crm_case_create_confirm_flow(client, auth_headers):
    h = _h(auth_headers, "e001")
    cid = _conv(client, h, "it_support")
    # Turn 1: intent → fields collected → confirm prompt (no write yet)
    lines, text = _send(client, h, cid, "open a crm case about delayed vendor invoice approvals")
    assert "Confirm" in text
    assert "CASE-" not in text
    # Turn 2: explicit confirmation → case created
    lines, text = _send(client, h, cid, "yes")
    assert "CASE-" in text


def test_crm_case_create_requires_confirmation(client, auth_headers):
    h = _h(auth_headers, "e001")
    cid = _conv(client, h, "it_support")
    _send(client, h, cid, "open a crm case about unreconciled card charges")
    # Cancel → nothing created
    _, text = _send(client, h, cid, "no")
    assert "cancelled" in text.lower()
    _, text = _send(client, h, cid, "show my CRM cases")
    assert "unreconciled" not in text


def test_crm_case_create_duplicate_reused(client, auth_headers):
    h = _h(auth_headers, "e001")
    cid = _conv(client, h, "it_support")
    _send(client, h, cid, "open a crm case about vendor onboarding access")
    _send(client, h, cid, "yes")
    # Same subject again → duplicate path reuses CASE-7001
    cid2 = _conv(client, h, "it_support")
    _, text = _send(client, h, cid2, "open a crm case about vendor onboarding access")
    assert "CASE-7001" in text or "already have" in text


def test_crm_case_create_disabled_in_hr(client, auth_headers):
    h = _h(auth_headers, "e002")
    cid = _conv(client, h, "hr_support")
    _, text = _send(client, h, cid, "open a crm case about benefits enrollment")
    assert "isn't enabled" in text or "disabled" in text.lower()


def test_analytics_phase6_fields(client, auth_headers):
    r = client.get("/v1/admin/analytics", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "by_department" in body and "funnel" in body and "unmet_needs" in body
    assert {"users", "conversations", "user_messages", "feedback"} <= set(body["funnel"])


def test_admin_usecases_self_service(client, auth_headers, get_store):
    r = client.get("/v1/admin/usecases", headers=auth_headers)
    assert r.status_code == 200
    ids = [u["usecase_id"] for u in r.json()["usecases"]]
    assert ids == ["finance_support", "hr_support", "it_support"]
    detail = client.get("/v1/admin/usecases/finance_support", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["config"]["department"] == "Finance"
    assert any(d["doc_id"].startswith("KB-FIN") for d in body["documents"])


def test_admin_usecases_requires_admin(client):
    r = client.get("/v1/admin/usecases", headers={"X-Demo-Employee": "e001"})
    assert r.status_code == 403
