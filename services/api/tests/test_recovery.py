import hashlib
import json
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
from app.tool_policy import ToolDenied, approval_scope
from app.tool_runner import report_bytes
from app.worker import run_once


def test_malformed_read_receipt_is_denied_before_report_write(tmp_path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'malformed.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        task = Task(goal="Reject corrupt receipt", state="running", workspace_path=str(DEMO_WORKSPACE))
        db.add(task)
        db.flush()
        read = PlanStep(task_id=task.id, ordinal=1, description="Read brief", tool_name="read_file", args_json='{"path":"brief.md"}', args_hash=args_hash({"path": "brief.md"}), risk_level="low", state="completed")
        db.add(read)
        db.flush()
        db.add(Execution(step_id=read.id, attempt=1, idempotency_key=approval_scope(task, read), status="completed", result_json="not JSON"))
        db.flush()
        with pytest.raises(ToolDenied, match="receipt is invalid"):
            report_bytes(db, task)
    engine.dispose()


@pytest.mark.parametrize("file_state", ["matches", "matches_with_followup", "matches_expired_followup", "matches_cancelled", "absent", "mismatch", "unsafe"])
def test_operator_resolves_only_verified_uncertain_report(tmp_path, monkeypatch, file_state) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'recovery.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    source = (DEMO_WORKSPACE / "brief.md").read_text(encoding="utf-8")
    with factory() as db:
        task = Task(goal="Resolve an uncertain report", state="cancelled" if file_state == "matches_cancelled" else "failed", workspace_path=str(DEMO_WORKSPACE), capabilities_json='["read_file","write_report"]', input_files_json='["brief.md"]', plan_version=1, deadline_at=utc_now() - timedelta(seconds=1) if file_state == "matches_expired_followup" else None)
        db.add(task)
        db.flush()
        read = PlanStep(task_id=task.id, ordinal=1, description="Read brief", tool_name="read_file", args_json='{"path":"brief.md"}', args_hash=args_hash({"path": "brief.md"}), risk_level="low", state="completed")
        write = PlanStep(task_id=task.id, ordinal=2, description="Write report", tool_name="write_report", args_json='{"filename":"report.md"}', args_hash=args_hash({"filename": "report.md"}), risk_level="high", state="needs_review", dependencies_json="[1]")
        db.add_all([read, write])
        if file_state in {"matches_with_followup", "matches_expired_followup"}:
            db.add(PlanStep(task_id=task.id, ordinal=3, description="Search after recovery", tool_name="search_local_docs", args_json='{"query":"Atlas"}', args_hash=args_hash({"query": "Atlas"}), risk_level="low", state="pending", dependencies_json="[2]"))
            task.capabilities_json = '["read_file","write_report","search_local_docs"]'
        db.flush()
        db.add(Execution(step_id=read.id, attempt=1, idempotency_key=approval_scope(task, read), status="completed", result_json=json.dumps({"source": "brief.md", "content": source, "sha256": hashlib.sha256(source.encode()).hexdigest()})))
        db.add(Execution(step_id=write.id, attempt=1, idempotency_key=approval_scope(task, write), status="needs_review"))
        db.flush()
        expected = report_bytes(db, task)
        task_id, step_id = task.id, write.id
        db.commit()
    target = tmp_path / "artifacts" / task_id / "report.md"
    if file_state != "absent":
        target.parent.mkdir(parents=True)
        if file_state == "unsafe":
            target.mkdir()
        else:
            target.write_bytes(expected if file_state.startswith("matches") else b"Unexpected report")
    monkeypatch.setattr("app.recovery.get_settings", lambda: SimpleNamespace(data_dir=str(tmp_path)))
    monkeypatch.setattr("app.operations.get_settings", lambda: SimpleNamespace(data_dir=str(tmp_path)))

    def test_db() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        client = TestClient(app, base_url="http://127.0.0.1:8765")
        headers = {"x-nexus-intent": "local", "origin": "http://127.0.0.1:5173"}
        inspection = client.get(f"/api/v1/tasks/{task_id}/recovery")
        assert inspection.status_code == 200
        assert inspection.json()["status"] == ("matches" if file_state.startswith("matches_") else file_state)
        body = {"step_id": step_id, "decision": "accept_existing", "expected_sha256": inspection.json()["expected_sha256"]}
        if file_state.startswith("matches"):
            assert client.post(f"/api/v1/tasks/{task_id}/recovery", headers=headers, json={**body, "expected_sha256": "0" * 64}).status_code == 409
            resolved = client.post(f"/api/v1/tasks/{task_id}/recovery", headers=headers, json=body)
            assert resolved.status_code == 200
            expected_state = "queued" if file_state == "matches_with_followup" else "failed" if file_state == "matches_expired_followup" else "cancelled" if file_state == "matches_cancelled" else "completed"
            assert resolved.json()["task_state"] == expected_state
            artifacts = client.get(f"/api/v1/tasks/{task_id}/artifacts").json()
            assert len(artifacts) == 1
            assert client.get(f"/api/v1/artifacts/{artifacts[0]['id']}").content == expected
            assert client.post(f"/api/v1/tasks/{task_id}/recovery", headers=headers, json=body).status_code == 409
            if file_state == "matches_with_followup":
                with factory() as db:
                    assert run_once(db)
                    assert db.get(Task, task_id).state == "completed"
        else:
            assert client.post(f"/api/v1/tasks/{task_id}/recovery", headers=headers, json=body).status_code == 409
            if file_state == "absent":
                resolved = client.post(f"/api/v1/tasks/{task_id}/recovery", headers=headers, json={**body, "decision": "confirm_absent"})
                assert resolved.status_code == 200
                assert resolved.json()["task_state"] == "failed"
                assert client.get(f"/api/v1/tasks/{task_id}/artifacts").json() == []
            else:
                assert client.post(f"/api/v1/tasks/{task_id}/recovery", headers=headers, json={**body, "decision": "confirm_absent"}).status_code == 409
            if file_state == "mismatch":
                assert target.read_bytes() == b"Unexpected report"
            elif file_state == "unsafe":
                assert target.is_dir()
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
