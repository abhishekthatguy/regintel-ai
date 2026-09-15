"""Phase 5 expansion tests: CRM tool, third-department config-only onboarding,
Genesys suggest surface."""


def _stream(client, headers, cid, msg):
    lines = []
    with client.stream(
        "POST", f"/v1/conversations/{cid}/messages:stream",
        headers=headers, json={"content": msg},
    ) as r:
        assert r.status_code == 200
        for line in r.iter_lines():
            if line:
                lines.append(line)
    return lines


def _conv(client, headers, usecase):
    r = client.post("/v1/conversations", headers=headers,
                    json={"usecase_id": usecase})
    assert r.status_code == 201
    return r.json()["conversation_id"]


def test_crm_lookup_by_case_id(client, auth_headers):
    h1 = dict(auth_headers)
    h1["X-Demo-Employee"] = "e001"
    cid = _conv(client, h1, "it_support")
    lines = _stream(client, h1, cid, "check my case CASE-7001")
    assert any('"crm_lookup"' in line for line in lines)
    assert any("CASE-7001" in line for line in lines)


def test_crm_lookup_scoped_to_employee(client, auth_headers):
    """e001's seeded case must not be visible to e002."""
    h2 = dict(auth_headers)
    h2["X-Demo-Employee"] = "e002"
    cid = _conv(client, h2, "it_support")
    lines = _stream(client, h2, cid, "check my case CASE-7001")
    assert any('"crm_lookup"' in line for line in lines)
    assert not any("CASE-7001" in line for line in lines)


def test_crm_lookup_disabled_in_hr_usecase(client, auth_headers):
    """Allowlist enforcement: crm_lookup is disabled in hr_support."""
    h2 = dict(auth_headers)
    h2["X-Demo-Employee"] = "e002"
    cid = _conv(client, h2, "hr_support")
    lines = _stream(client, h2, cid, "check my case CASE-7004")
    assert not any('"crm_lookup"' in line for line in lines)


def test_finance_usecase_config_only(client, auth_headers):
    """UJ-07: third department works via config+content only — no new logic."""
    h3 = dict(auth_headers)
    h3["X-Demo-Employee"] = "e003"
    cid = _conv(client, h3, "finance_support")
    lines = _stream(client, h3, cid, "how do I submit an expense report")
    assert any('"citation"' in line for line in lines)


def test_genesys_suggest_endpoint(client, auth_headers, get_store):
    r = client.post("/v1/integrations/genesys/suggest",
                    headers=auth_headers,
                    json={"utterance": "how do I connect to VPN"})
    assert r.status_code == 200
    body = r.json()
    assert body["citations"], "suggest should return grounded citations"
    assert body["suggestion"]


def test_genesys_suggest_stub_default_identity(client, get_store):
    """Stub auth falls back to the default employee; JWT mode (tested in
    test_security.py) is what a real Genesys data action would use."""
    r = client.post("/v1/integrations/genesys/suggest",
                    json={"utterance": "vpn"})
    assert r.status_code == 200
