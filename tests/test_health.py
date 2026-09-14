def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ready(client):
    resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["checks"]["database"] is True
    assert body["checks"]["usecase_config"] is True


def test_correlation_id_generated(client):
    resp = client.get("/health")
    assert resp.headers["x-correlation-id"]


def test_correlation_id_echoed(client):
    resp = client.get("/health", headers={"X-Correlation-ID": "test-corr-123"})
    assert resp.headers["x-correlation-id"] == "test-corr-123"
