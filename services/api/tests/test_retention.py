from collections.abc import Generator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, get_db, make_engine
from app.main import app
from app.models import Approval, Artifact, Event, Execution, PlanStep, Task, utc_now
from app.planning import args_hash
from app.retention import RetentionError, prune_old_tasks, task_owned_dir


def test_confirmed_delete_removes_task_data_without_touching_external_workspace(tmp_path, monkeypatch) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'retention.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    data_dir = tmp_path / "data"
    external = tmp_path / "external"
    external.mkdir()
    (external / "keep.md").write_text("Keep this", encoding="utf-8")
    monkeypatch.setattr("app.tasks.get_settings", lambda: type("Settings", (), {"data_dir": str(data_dir)})())
    with factory() as db:
        task = Task(goal="Delete my records", state="completed", workspace_path=str(external), capabilities_json='["write_report"]')
        db.add(task)
        db.flush()
        step = PlanStep(task_id=task.id, ordinal=1, description="Write report", tool_name="write_report", args_json='{"filename":"report.md"}', args_hash=args_hash({"filename": "report.md"}), risk_level="high")
        db.add(step)
        db.flush()
        db.add(Approval(step_id=step.id, scope_hash="a" * 64, requested_action="Write report", decision="approved"))
        db.add(Execution(step_id=step.id, attempt=1, idempotency_key="b" * 64, status="completed"))
        db.add(Event(task_id=task.id, kind="task_created", payload_json="{}", correlation_id="test"))
        artifact = data_dir / "artifacts" / task.id / "report.md"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("Report", encoding="utf-8")
        db.add(Artifact(task_id=task.id, safe_path=str(artifact), sha256="c" * 64, media_type="text/markdown", size_bytes=6))
        inputs = data_dir / "inputs" / task.id
        inputs.mkdir(parents=True)
        (inputs / "note.md").write_text("Input", encoding="utf-8")
        active = Task(goal="Keep active task", state="queued")
        db.add(active)
        db.commit()

    def test_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    try:
        client = TestClient(app, base_url="http://127.0.0.1:8765")
        headers = {"x-nexus-intent": "local"}
        assert client.request("DELETE", f"/api/v1/tasks/{task.id}", headers=headers, json={"confirm_id": "wrong"}).status_code == 422
        assert client.request("DELETE", f"/api/v1/tasks/{active.id}", headers=headers, json={"confirm_id": active.id}).status_code == 409
        assert client.request("DELETE", f"/api/v1/tasks/{task.id}", headers=headers, json={"confirm_id": task.id}).status_code == 204
        uploaded = client.post("/api/v1/tasks", headers=headers, json={"goal": "Delete uploaded task files", "input_files": [{"name": "private.md", "content": "Private task input"}]}).json()
        uploaded_dir = Path(uploaded["workspace_path"])
        assert (uploaded_dir / "private.md").read_text(encoding="utf-8") == "Private task input"
        assert client.request("DELETE", f"/api/v1/tasks/{uploaded['id']}", headers=headers, json={"confirm_id": uploaded["id"]}).status_code == 204
        assert not uploaded_dir.exists()
        assert client.get(f"/api/v1/tasks/{task.id}").status_code == 404
        assert not artifact.exists()
        assert not inputs.exists()
        assert (external / "keep.md").read_text(encoding="utf-8") == "Keep this"
        with factory() as db:
            assert db.get(Task, task.id) is None
            assert db.get(PlanStep, step.id) is None
            assert db.query(Execution).count() == 0
            assert db.query(Approval).count() == 0
            assert db.query(Event).count() == 0
            assert db.query(Artifact).count() == 0
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_delete_scope_rejects_redirected_owned_directory(tmp_path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (data / "inputs").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable on this host")
    with pytest.raises(RetentionError, match="redirected"):
        task_owned_dir(data, "inputs", "task")


def test_opt_in_retention_prunes_only_old_terminal_tasks(tmp_path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'age.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = utc_now()
    external = tmp_path / "selected"
    external.mkdir()
    (external / "keep.md").write_text("Keep", encoding="utf-8")
    with factory() as db:
        old = Task(goal="Old completed task", state="completed", completed_at=now - timedelta(days=40), workspace_path=str(external))
        recent = Task(goal="Recent completed task", state="completed", completed_at=now - timedelta(days=10))
        draft = Task(goal="Old draft task", state="draft", completed_at=now - timedelta(days=40))
        db.add_all([old, recent, draft])
        db.commit()
        owned = tmp_path / "data" / "artifacts" / old.id
        owned.mkdir(parents=True)
        (owned / "report.md").write_text("Delete", encoding="utf-8")
        assert prune_old_tasks(db, str(tmp_path / "data"), 0, now) == 0
        assert db.get(Task, old.id) is not None
        assert prune_old_tasks(db, str(tmp_path / "data"), 30, now) == 1
        assert db.get(Task, old.id) is None
        assert db.get(Task, recent.id) is not None
        assert db.get(Task, draft.id) is not None
        assert not owned.exists()
        assert (external / "keep.md").read_text(encoding="utf-8") == "Keep"
    engine.dispose()
