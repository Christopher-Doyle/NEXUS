import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app import recovery, worker
from app.db import Base, begin_write, make_engine
from app.models import Approval, Artifact, Execution, PlanStep, Task, utc_now
from app.planning import args_hash
from app.registry import REGISTRY
from app.tasks import DEMO_WORKSPACE
from app.tool_policy import approval_scope


def slow_read_child(sender) -> None:
    from app import worker as child_worker

    def stall(*_args):
        time.sleep(10)

    child_worker.run_tool = stall
    child_worker._run_once_process(sender)


def slow_write_child(sender) -> None:
    from app import worker as child_worker

    original = child_worker.run_tool

    def stall_after_write(db, task, step):
        result = original(db, task, step)
        time.sleep(10)
        return result

    child_worker.run_tool = stall_after_write
    child_worker._run_once_process(sender)


def slow_before_write_child(sender) -> None:
    from app import worker as child_worker

    def stall(*_args):
        time.sleep(10)

    child_worker.run_tool = stall
    child_worker._run_once_process(sender)


def test_supervisor_times_out_a_read_without_leaving_a_worker(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'read_timeout.db'}"
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setattr(worker, "SessionLocal", factory)
    monkeypatch.setitem(REGISTRY, "read_file", replace(REGISTRY["read_file"], timeout_seconds=1))
    with factory() as db:
        task = Task(goal="Timeout a read safely", state="queued", workspace_path=str(DEMO_WORKSPACE), capabilities_json='["read_file"]', input_files_json='["brief.md"]', plan_version=1)
        db.add(task)
        db.flush()
        step = PlanStep(task_id=task.id, ordinal=1, description="Read brief", tool_name="read_file", args_json='{"path":"brief.md"}', args_hash=args_hash({"path": "brief.md"}), risk_level="low", state="pending")
        db.add(step)
        db.flush()
        task_id, step_id = task.id, step.id
        db.commit()
    assert worker.run_once_bounded(slow_read_child)
    with factory() as db:
        execution = db.scalar(select(Execution).where(Execution.step_id == step_id))
        assert db.get(Task, task_id).state == "failed"
        assert db.get(PlanStep, step_id).state == "failed"
        assert execution.status == "failed" and execution.error_code == "ToolTimeout"
        assert execution.ended_at is not None
    engine.dispose()


def test_cancelled_task_stays_cancelled_when_read_times_out(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'cancel_timeout.db'}"
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setattr(worker, "SessionLocal", factory)
    monkeypatch.setitem(REGISTRY, "read_file", replace(REGISTRY["read_file"], timeout_seconds=2))
    with factory() as db:
        task = Task(goal="Cancel a hanging read", state="queued", workspace_path=str(DEMO_WORKSPACE), capabilities_json='["read_file"]', input_files_json='["brief.md"]', plan_version=1)
        db.add(task)
        db.flush()
        step = PlanStep(task_id=task.id, ordinal=1, description="Read brief", tool_name="read_file", args_json='{"path":"brief.md"}', args_hash=args_hash({"path": "brief.md"}), risk_level="low", state="pending")
        db.add(step)
        db.flush()
        task_id, step_id = task.id, step.id
        db.commit()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker.run_once_bounded, slow_read_child)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with factory() as db:
                if db.scalar(select(Execution).where(Execution.step_id == step_id)) is not None:
                    break
            time.sleep(0.05)
        else:
            raise AssertionError("Worker did not claim the read")
        with factory() as db:
            begin_write(db)
            db.get(Task, task_id).state = "cancelled"
            db.commit()
        assert future.result(timeout=10)
    with factory() as db:
        execution = db.scalar(select(Execution).where(Execution.step_id == step_id))
        assert db.get(Task, task_id).state == "cancelled"
        assert execution.error_code == "ToolTimeout"
    engine.dispose()


@pytest.mark.parametrize("write_phase", ["before", "after"])
def test_supervisor_handles_uncertain_write_timeout(tmp_path, monkeypatch, write_phase) -> None:
    database_url = f"sqlite:///{tmp_path / 'write_timeout.db'}"
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(worker, "SessionLocal", factory)
    monkeypatch.setitem(REGISTRY, "write_report", replace(REGISTRY["write_report"], timeout_seconds=1))
    source = (DEMO_WORKSPACE / "brief.md").read_text(encoding="utf-8")
    with factory() as db:
        task = Task(goal="Timeout an approved report", state="running", workspace_path=str(DEMO_WORKSPACE), capabilities_json='["read_file","write_report"]', input_files_json='["brief.md"]', plan_version=1)
        db.add(task)
        db.flush()
        read = PlanStep(task_id=task.id, ordinal=1, description="Read brief", tool_name="read_file", args_json='{"path":"brief.md"}', args_hash=args_hash({"path": "brief.md"}), risk_level="low", state="completed")
        write = PlanStep(task_id=task.id, ordinal=2, description="Write report", tool_name="write_report", args_json='{"filename":"report.md"}', args_hash=args_hash({"filename": "report.md"}), risk_level="high", state="pending", dependencies_json="[1]")
        db.add_all([read, write])
        db.flush()
        db.add(Execution(step_id=read.id, attempt=1, idempotency_key=approval_scope(task, read), status="completed", result_json=json.dumps({"source": "brief.md", "content": source, "sha256": hashlib.sha256(source.encode()).hexdigest()})))
        db.add(Approval(step_id=write.id, scope_hash=approval_scope(task, write), requested_action="Write report.md", decision="approved", expires_at=utc_now() + timedelta(hours=1)))
        task_id, step_id = task.id, write.id
        db.commit()
    assert worker.run_once_bounded(slow_write_child if write_phase == "after" else slow_before_write_child)
    report = tmp_path / "artifacts" / task_id / "report.md"
    assert report.is_file() == (write_phase == "after")
    with factory() as db:
        execution = db.scalar(select(Execution).where(Execution.step_id == step_id))
        assert db.get(Task, task_id).state == "failed"
        assert db.get(PlanStep, step_id).state == "needs_review"
        assert execution.status == "needs_review" and execution.error_code == "ToolTimeout"
        assert db.scalar(select(Artifact).where(Artifact.task_id == task_id)) is None
    monkeypatch.setattr(recovery, "get_settings", lambda: SimpleNamespace(data_dir=str(tmp_path)))
    with factory() as db:
        inspection = recovery.recovery_status(task_id, db)
        assert inspection["status"] == ("matches" if write_phase == "after" else "absent")
    with factory() as db:
        decision = "accept_existing" if write_phase == "after" else "confirm_absent"
        resolved = recovery.resolve_recovery(task_id, recovery.RecoveryDecision(step_id=step_id, decision=decision, expected_sha256=inspection["expected_sha256"]), db)
        assert resolved["task_state"] == ("completed" if write_phase == "after" else "failed")
        assert (db.scalar(select(Artifact).where(Artifact.task_id == task_id)) is not None) == (write_phase == "after")
    if write_phase == "after":
        assert list(report.parent.iterdir()) == [report]
    engine.dispose()
