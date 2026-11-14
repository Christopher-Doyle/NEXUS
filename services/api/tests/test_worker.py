from collections.abc import Generator
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, get_db, make_engine
from app.main import app
from app.models import Execution, PlanStep, Task, utc_now
from app.planning import args_hash
from app.tasks import DEMO_WORKSPACE
from app.tool_policy import ToolDenied, approval_scope, workspace_file
from app.worker import run_once


def test_workspace_rejects_traversal(tmp_path) -> None:
    (tmp_path / "note.md").write_text("example")
    assert workspace_file(str(tmp_path), "note.md").name == "note.md"
    with pytest.raises(ToolDenied):
        workspace_file(str(tmp_path), "../secret.md")


def test_demo_execution_requires_exact_approval(tmp_path, monkeypatch) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'worker.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr("app.tool_runner.get_settings", lambda: SimpleNamespace(data_dir=str(tmp_path)))
    monkeypatch.setattr("app.operations.get_settings", lambda: SimpleNamespace(data_dir=str(tmp_path)))

    def test_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    try:
        client = TestClient(app, base_url="http://127.0.0.1:8765")
        headers = {"x-nexus-intent": "local", "origin": "http://127.0.0.1:5173"}
        created = client.post("/api/v1/tasks", headers=headers, json={"goal": "Write a sample report"}).json()
        task_id = created["id"]
        assert client.post(f"/api/v1/tasks/{task_id}/plan", headers=headers).status_code == 202
        assert client.post(f"/api/v1/tasks/{task_id}/start", headers=headers).status_code == 202
        for _ in range(3):
            with factory() as db:
                assert run_once(db)
        pending = client.get("/api/v1/approvals").json()
        snapshot = client.get(f"/api/v1/tasks/{task_id}").json()
        assert pending, (snapshot["state"], [(step["tool_name"], step["state"]) for step in snapshot["steps"]])
        approval = pending[0]
        assert client.get(f"/api/v1/tasks/{task_id}").json()["state"] == "waiting_approval"
        wrong = client.post(f"/api/v1/approvals/{approval['id']}/decision", headers=headers, json={"decision": "approved", "scope_hash": "0" * 64})
        assert wrong.status_code == 409
        accepted = client.post(f"/api/v1/approvals/{approval['id']}/decision", headers=headers, json={"decision": "approved", "scope_hash": approval["scope_hash"]})
        assert accepted.status_code == 200
        with factory() as db:
            assert run_once(db)
        assert client.get(f"/api/v1/tasks/{task_id}").json()["state"] == "completed"
        report = (tmp_path / "artifacts" / task_id / "project-report.md")
        assert report.exists()
        assert "Atlas" in report.read_text(encoding="utf-8")
        artifacts = client.get(f"/api/v1/tasks/{task_id}/artifacts").json()
        assert len(artifacts) == 1
        assert client.get(f"/api/v1/artifacts/{artifacts[0]['id']}").status_code == 200
        assert any(event["type"] == "step_completed" for event in client.get(f"/api/v1/tasks/{task_id}/journal").json())
        with factory() as db:
            assert not run_once(db)

        rejected_task = client.post("/api/v1/tasks", headers=headers, json={"goal": "Reject a sample report"}).json()["id"]
        client.post(f"/api/v1/tasks/{rejected_task}/plan", headers=headers)
        client.post(f"/api/v1/tasks/{rejected_task}/start", headers=headers)
        for _ in range(3):
            with factory() as db:
                assert run_once(db)
        rejected_approval = next(item for item in client.get("/api/v1/approvals").json() if item["task_id"] == rejected_task)
        denied = client.post(f"/api/v1/approvals/{rejected_approval['id']}/decision", headers=headers, json={"decision": "rejected", "scope_hash": rejected_approval["scope_hash"]})
        assert denied.status_code == 200
        assert client.get(f"/api/v1/tasks/{rejected_task}").json()["state"] == "failed"
        assert client.get(f"/api/v1/tasks/{rejected_task}/artifacts").json() == []
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_recovery_replays_read_but_stops_uncertain_write(tmp_path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'recovery.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        task = Task(goal="Recover a read", state="running", workspace_path=str(DEMO_WORKSPACE), capabilities_json='["read_file"]', input_files_json='["brief.md"]', plan_version=1)
        db.add(task)
        db.flush()
        read = PlanStep(task_id=task.id, ordinal=1, description="Read brief", tool_name="read_file", args_json='{"path":"brief.md"}', args_hash=args_hash({"path": "brief.md"}), risk_level="low", state="running")
        db.add(read)
        db.flush()
        db.add(Execution(step_id=read.id, attempt=1, idempotency_key=approval_scope(task, read), status="running", lease_until=utc_now() + timedelta(minutes=1)))
        db.commit()
    with factory() as db:
        assert not run_once(db)
        assert db.get(PlanStep, read.id).state == "running"
    with factory() as db:
        db.query(Execution).filter_by(step_id=read.id).one().lease_until = utc_now() - timedelta(seconds=1)
        db.commit()
    with factory() as db:
        assert run_once(db)
        assert db.get(Task, task.id).state == "completed"
        assert db.get(PlanStep, read.id).state == "completed"

    with factory() as db:
        task = Task(goal="Recover a write", state="running", workspace_path=str(DEMO_WORKSPACE), capabilities_json='["write_report"]', plan_version=1)
        db.add(task)
        db.flush()
        write = PlanStep(task_id=task.id, ordinal=1, description="Write report", tool_name="write_report", args_json='{"filename":"report.md"}', args_hash=args_hash({"filename": "report.md"}), risk_level="high", state="running")
        db.add(write)
        db.flush()
        db.add(Execution(step_id=write.id, attempt=1, idempotency_key=approval_scope(task, write), status="running", lease_until=utc_now() - timedelta(seconds=1)))
        db.commit()
    with factory() as db:
        assert run_once(db)
        assert db.get(Task, task.id).state == "failed"
        assert db.get(PlanStep, write.id).state == "needs_review"
    engine.dispose()
