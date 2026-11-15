from collections.abc import Generator
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, get_db, make_engine
from app.main import app


def test_local_settings_persist_and_bound_new_task_deadline(tmp_path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'preferences.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def test_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    try:
        client = TestClient(app, base_url="http://127.0.0.1:8765")
        headers = {"x-nexus-intent": "local"}
        before = client.get("/api/v1/settings").json()
        assert before["network_access_enabled"] is False
        assert client.patch("/api/v1/settings", json={"ollama_model": "qwen3.5:9b"}).status_code == 403
        assert client.patch("/api/v1/settings", headers=headers, json={"network_access_enabled": True}).status_code == 422
        assert client.patch("/api/v1/settings", headers=headers, json={"ollama_model": "model with spaces"}).status_code == 422
        updated = client.patch("/api/v1/settings", headers=headers, json={"ollama_model": "qwen3.5:9b", "ollama_timeout_seconds": 45, "task_timeout_seconds": 120})
        assert updated.status_code == 200
        assert updated.json()["task_timeout_seconds"] == 120
        assert client.get("/api/v1/settings").json()["ollama_model"] == "qwen3.5:9b"
        created = client.post("/api/v1/tasks", headers=headers, json={"goal": "Prepare a synthetic report"}).json()
        assert client.post(f"/api/v1/tasks/{created['id']}/plan", headers=headers).status_code == 202
        started = client.post(f"/api/v1/tasks/{created['id']}/start", headers=headers)
        assert started.status_code == 202
        deadline = datetime.fromisoformat(started.json()["deadline_at"]).astimezone(UTC)
        remaining = (deadline - datetime.now(UTC)).total_seconds()
        assert 115 <= remaining <= 120
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
