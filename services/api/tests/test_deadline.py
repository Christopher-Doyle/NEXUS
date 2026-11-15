from collections.abc import Generator
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, get_db, make_engine
from app.main import app
from app.models import Approval, Event, PlanStep, Task, utc_now
from app.planning import args_hash
from app.tasks import DEMO_WORKSPACE
from app.tool_policy import approval_scope
from app.worker import run_once


def test_expired_queue_and_approval_are_failed_without_tool_execution(tmp_path, monkeypatch) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'deadline.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    expired_at = utc_now() - timedelta(seconds=1)
    with factory() as db:
        queued = Task(goal="Expired queued task", state="queued", deadline_at=expired_at, workspace_path=str(DEMO_WORKSPACE), capabilities_json='["read_file"]', input_files_json='["brief.md"]', plan_version=1)
        db.add(queued)
        db.flush()
        read = PlanStep(task_id=queued.id, ordinal=1, description="Read brief", tool_name="read_file", args_json='{"path":"brief.md"}', args_hash=args_hash({"path": "brief.md"}), risk_level="low", state="pending")
        db.add(read)
        waiting = Task(goal="Expired approval task", state="waiting_approval", deadline_at=expired_at, workspace_path=str(DEMO_WORKSPACE), capabilities_json='["write_report"]', plan_version=1)
        db.add(waiting)
        db.flush()
        write = PlanStep(task_id=waiting.id, ordinal=1, description="Write report", tool_name="write_report", args_json='{"filename":"report.md"}', args_hash=args_hash({"filename": "report.md"}), risk_level="high", state="pending")
        db.add(write)
        db.flush()
        approval = Approval(step_id=write.id, scope_hash=approval_scope(waiting, write), requested_action="Write report", decision="pending", expires_at=utc_now() + timedelta(minutes=1))
        db.add(approval)
        db.commit()

    monkeypatch.setattr("app.worker.run_tool", lambda *_: (_ for _ in ()).throw(AssertionError("Expired task executed")))
    with factory() as db:
        assert run_once(db)
    with factory() as db:
        assert db.get(Task, queued.id).state == "failed"
        assert db.get(PlanStep, read.id).state == "pending"

    def test_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    try:
        client = TestClient(app, base_url="http://127.0.0.1:8765")
        response = client.post(f"/api/v1/approvals/{approval.id}/decision", headers={"x-nexus-intent": "local"}, json={"decision": "approved", "scope_hash": approval.scope_hash})
        assert response.status_code == 409
        with factory() as db:
            assert db.get(Task, waiting.id).state == "failed"
            assert db.query(Event).filter_by(task_id=waiting.id, kind="task_timeout").count() == 1
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
