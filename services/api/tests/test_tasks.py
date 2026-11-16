from collections.abc import Generator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, get_db, make_engine
from app.main import app


def test_upload_rejects_redirected_storage_root(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (data_dir / "workspaces").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable on this host")
    engine = make_engine(f"sqlite:///{tmp_path / 'redirected.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr("app.tasks.get_settings", lambda: SimpleNamespace(data_dir=str(data_dir), approved_workspaces=""))

    def test_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    try:
        client = TestClient(app, base_url="http://127.0.0.1:8765")
        result = client.post("/api/v1/tasks", headers={"x-nexus-intent": "local"}, json={"goal": "Reject redirected upload", "input_files": [{"name": "brief.md", "content": "Private text"}]})
        assert result.status_code == 403
        assert list(outside.iterdir()) == []
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


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
        network = client.post("/api/v1/tasks", headers=headers, json={"goal": "Request outbound fetch", "network_access": True})
        assert network.status_code == 422
        missing_consent = client.post("/api/v1/tasks", headers=headers, json={"goal": "Request outbound fetch", "capabilities": ["fetch_url"]})
        assert missing_consent.status_code == 422
        scoped_network = client.post("/api/v1/tasks", headers=headers, json={"goal": "Review public HTTPS source", "capabilities": ["fetch_url"], "network_access": True})
        assert scoped_network.status_code == 201
        assert scoped_network.json()["network_access"] is True
        oversized = client.post("/api/v1/tasks", headers=headers, json={"goal": "Reject huge constraint", "constraints": ["x" * 501]})
        assert oversized.status_code == 422
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
        assert client.get("/api/v1/tasks", params={"state": "review_required", "q": "sample"}).json()["total"] == 1
        assert client.get("/api/v1/tasks", params={"state": "completed"}).json()["total"] == 0
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_attached_input_is_planned_and_unapproved_folder_is_denied(tmp_path, monkeypatch) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'inputs.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr("app.tasks.get_settings", lambda: SimpleNamespace(data_dir=str(tmp_path), approved_workspaces=""))

    def test_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    try:
        client = TestClient(app, base_url="http://127.0.0.1:8765")
        headers = {"x-nexus-intent": "local"}
        denied = client.post("/api/v1/tasks", headers=headers, json={"goal": "Read private notes", "workspace_path": str(tmp_path)})
        assert denied.status_code == 403
        blocked_network = client.post("/api/v1/tasks", headers=headers, json={"goal": "Reject network folder", "workspace_path": "\\\\server\\share"})
        assert blocked_network.status_code == 422
        approved = tmp_path / "approved"
        approved.mkdir()
        (approved / "notes.md").write_text("Approved local notes", encoding="utf-8")
        monkeypatch.setattr("app.tasks.get_settings", lambda: SimpleNamespace(data_dir=str(tmp_path), approved_workspaces=str(approved)))
        selected = client.post("/api/v1/tasks", headers=headers, json={"goal": "Read approved local notes", "workspace_path": str(approved)})
        assert selected.status_code == 201
        assert selected.json()["input_files"] == ["notes.md"]
        created = client.post("/api/v1/tasks", headers=headers, json={"goal": "Read the attached notes", "input_files": [{"name": "notes.md", "content": "Synthetic notes"}]})
        assert created.status_code == 201
        assert created.json()["input_files"] == ["notes.md"]
        planned = client.post(f"/api/v1/tasks/{created.json()['id']}/plan", headers=headers)
        assert [step["tool_name"] for step in planned.json()["steps"]] == ["read_file", "write_report"]
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
