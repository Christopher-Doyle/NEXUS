from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, get_db, make_engine
from app.main import app


def test_task_planning_and_editing(tmp_path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    try:
        client = TestClient(app, base_url="http://127.0.0.1:8765")
        headers = {"x-nexus-intent": "local", "origin": "http://127.0.0.1:5173"}
        blocked = client.post("/api/v1/tasks", json={"goal": "Create a sample report"})
        assert blocked.status_code == 403
        created = client.post("/api/v1/tasks", headers=headers, json={"goal": "Create a sample report"})
        assert created.status_code == 201
        task_id = created.json()["id"]
        assert created.json()["state"] == "draft"
        planned = client.post(f"/api/v1/tasks/{task_id}/plan", headers=headers)
        assert planned.status_code == 202
        assert planned.json()["state"] == "review_required"
        assert len(planned.json()["steps"]) == 3
        version = planned.json()["plan_version"]
        edited = client.patch(f"/api/v1/tasks/{task_id}/steps", headers=headers, json={
            "plan_version": version,
            "steps": [{"description": "Read the brief", "tool_name": "read_file", "args": {"path": "brief.md"}}],
        })
        assert edited.status_code == 200
        assert edited.json()["plan_version"] == version + 1
        conflict = client.patch(f"/api/v1/tasks/{task_id}/steps", headers=headers, json={
            "plan_version": version,
            "steps": [{"description": "Read the brief", "tool_name": "read_file", "args": {"path": "brief.md"}}],
        })
        assert conflict.status_code == 409
        invalid = client.patch(f"/api/v1/tasks/{task_id}/steps", headers=headers, json={
            "plan_version": version + 1,
            "steps": [{"description": "Escape workspace", "tool_name": "read_file", "args": {"path": "C:/secret.txt"}}],
        })
        assert invalid.status_code == 422
        fetched = client.get(f"/api/v1/tasks/{task_id}")
        assert fetched.json()["plan_version"] == version + 1
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
