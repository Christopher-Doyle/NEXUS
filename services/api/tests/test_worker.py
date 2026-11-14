import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event, Lock
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
        library = client.get("/api/v1/artifacts").json()
        assert library["total"] == 1
        assert library["items"][0]["task_id"] == task_id
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


def test_simultaneous_workers_do_not_repeat_a_leased_read(tmp_path, monkeypatch) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'concurrent.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        task = Task(goal="Read once", state="queued", workspace_path=str(DEMO_WORKSPACE), capabilities_json='["read_file"]', input_files_json='["brief.md"]', plan_version=1)
        db.add(task)
        db.flush()
        step = PlanStep(task_id=task.id, ordinal=1, description="Read brief", tool_name="read_file", args_json='{"path":"brief.md"}', args_hash=args_hash({"path": "brief.md"}), risk_level="low", state="pending")
        db.add(step)
        db.commit()
    calls = 0
    lock = Lock()
    gate = Barrier(2)

    def slow_tool(_db, _task, _step):
        nonlocal calls
        with lock:
            calls += 1
        time.sleep(0.2)
        return {"bytes": 1}

    monkeypatch.setattr("app.worker.run_tool", slow_tool)

    def worker_try() -> bool:
        gate.wait()
        with factory() as db:
            return run_once(db)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: worker_try(), range(2)))
    assert sorted(results) == [False, True]
    assert calls == 1
    with factory() as db:
        assert db.get(Task, task.id).state == "completed"
        assert db.get(PlanStep, step.id).state == "completed"
    engine.dispose()


@pytest.mark.parametrize(("action", "final_state"), [("pause", "paused"), ("cancel", "cancelled")])
def test_pause_or_cancel_during_read_stops_following_step(tmp_path, monkeypatch, action, final_state) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / f'{action}.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        task = Task(goal="Read two files", state="running", workspace_path=str(DEMO_WORKSPACE), capabilities_json='["read_file"]', input_files_json='["brief.md","meeting.md"]', plan_version=1)
        db.add(task)
        db.flush()
        for ordinal, path in enumerate(["brief.md", "meeting.md"], start=1):
            db.add(PlanStep(task_id=task.id, ordinal=ordinal, description=f"Read {path}", tool_name="read_file", args_json=f'{{"path":"{path}"}}', args_hash=args_hash({"path": path}), risk_level="low", state="pending"))
        db.commit()
    entered = Event()
    release = Event()

    def slow_tool(_db, _task, _step):
        entered.set()
        assert release.wait(timeout=5)
        return {"bytes": 1}

    monkeypatch.setattr("app.worker.run_tool", slow_tool)

    def test_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    try:
        def worker_try() -> bool:
            with factory() as db:
                return run_once(db)

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker_try)
            assert entered.wait(timeout=5)
            client = TestClient(app, base_url="http://127.0.0.1:8765")
            response = client.post(f"/api/v1/tasks/{task.id}/{action}", headers={"x-nexus-intent": "local"})
            assert response.status_code == 202
            release.set()
            assert future.result(timeout=5)
        with factory() as db:
            assert db.get(Task, task.id).state == final_state
            assert [step.state for step in db.query(PlanStep).filter_by(task_id=task.id).order_by(PlanStep.ordinal)] == ["completed", "pending"]
            assert not run_once(db)
    finally:
        release.set()
        app.dependency_overrides.clear()
        engine.dispose()
