from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.rate_limit import RateLimiter


def test_local_host_origin_and_intent_boundary() -> None:
    local = TestClient(app, base_url="http://127.0.0.1:8765")
    remote_host = TestClient(app, base_url="http://nexus.invalid:8765")
    assert remote_host.post("/api/v1/missing", headers={"x-nexus-intent": "local"}).status_code == 403
    assert local.post("/api/v1/missing", headers={"x-nexus-intent": "local", "origin": "https://untrusted.example"}).status_code == 403
    assert local.post("/api/v1/missing", headers={"x-nexus-intent": "local", "origin": "null"}).status_code == 403
    assert local.post("/api/v1/missing", headers={"origin": "http://127.0.0.1:5173"}).status_code == 403
    assert local.post("/api/v1/missing", headers={"x-nexus-intent": "local", "origin": "http://127.0.0.1:5173"}).status_code == 404


def test_mutation_rate_limit_returns_retry_after(monkeypatch) -> None:
    monkeypatch.setattr("app.main.rate_limiter", RateLimiter(mutation_limit=1, planning_limit=1))
    client = TestClient(app, base_url="http://127.0.0.1:8765")
    headers = {"x-nexus-intent": "local"}
    assert client.post("/api/v1/missing", headers=headers).status_code == 404
    blocked = client.post("/api/v1/missing", headers=headers)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    assert blocked.json()["code"] == "rate_limited"
    assert client.get("/api/v1/missing").status_code == 404


def test_unexpected_error_is_redacted_and_correlated() -> None:
    def broken_db():
        raise RuntimeError("SECRET_TOKEN_SHOULD_NOT_LEAK")

    app.dependency_overrides[get_db] = broken_db
    try:
        client = TestClient(app, base_url="http://127.0.0.1:8765", raise_server_exceptions=False)
        response = client.get("/api/v1/settings")
        assert response.status_code == 500
        assert response.json()["code"] == "internal_error"
        assert response.json()["correlation_id"] == response.headers["X-Correlation-ID"]
        assert "SECRET_TOKEN" not in response.text
    finally:
        app.dependency_overrides.clear()
