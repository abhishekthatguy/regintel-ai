"""Phase 7 hardening: self-service knowledge upload, eval coverage for
CRM/finance journeys."""

GOOD_DOC = """---
doc_id: KB-IT-099
title: Test Upload Doc
department: IT
acl: [ALL]
version: "1.0"
source_system: local_files
source_url: "https://kb.internal/it/test-upload"
---
# Test Upload
## Overview
This document covers the widget calibration procedure for demo purposes.
"""


def test_knowledge_upload_and_retrieval(client, auth_headers):
    r = client.post("/v1/admin/knowledge", headers=auth_headers,
                    json={"filename": "test-upload.md", "content": GOOD_DOC})
    assert r.status_code == 201, r.text
    assert r.json()["doc_id"] == "KB-IT-099"
    # Now retrievable through the normal pipeline
    import json

    cid = client.post("/v1/conversations", headers=auth_headers,
                      json={"usecase_id": "it_support"}).json()["conversation_id"]
    text = ""
    with client.stream("POST", f"/v1/conversations/{cid}/messages:stream",
                       headers=auth_headers,
                       json={"content": "widget calibration procedure"}) as resp:
        for line in resp.iter_lines():
            if line:
                ev = json.loads(line)
                if ev["type"] == "token":
                    text += ev["data"]["text"]
    assert "calibrat" in text.lower()


def test_knowledge_upload_validation(client, auth_headers):
    bad = client.post("/v1/admin/knowledge", headers=auth_headers,
                      json={"filename": "x.md", "content": "no front matter"})
    assert bad.status_code == 422
    bad2 = client.post("/v1/admin/knowledge", headers=auth_headers,
                       json={"filename": "../evil.md", "content": GOOD_DOC})
    assert bad2.status_code == 422
    bad3 = client.post("/v1/admin/knowledge", headers=auth_headers,
                       json={"filename": "x.md",
                             "content": GOOD_DOC.replace("doc_id: KB-IT-099", "doc_id: nope")})
    assert bad3.status_code == 422


def test_knowledge_upload_requires_admin(client):
    r = client.post("/v1/admin/knowledge", headers={"X-Demo-Employee": "e001"},
                    json={"filename": "x.md", "content": GOOD_DOC})
    assert r.status_code == 403
