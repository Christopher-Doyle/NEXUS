import hashlib
import json
import multiprocessing
import time
from datetime import timedelta
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.models import Approval, Artifact, Execution, PlanStep, Task, utc_now
from app.planning import args_hash
from app.tasks import DEMO_WORKSPACE
from app.tool_policy import approval_scope
from app.worker import run_once


def process_worker(database_url: str, gate, expected: int) -> None:
    engine = make_engine(database_url)
    factory = sessionmaker(bind=engine)
    if not gate.wait(timeout=10):
        raise RuntimeError("Worker start gate timed out")
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        with factory() as db:
            run_once(db)
            completed = db.scalar(select(func.count()).select_from(Task).where(Task.state == "completed")) or 0
        if completed == expected:
            break
        time.sleep(0.01)
    engine.dispose()


def interrupted_read_worker(database_url: str, entered) -> None:
    from app import worker

    engine = make_engine(database_url)
    factory = sessionmaker(bind=engine)

    def blocked_read(*_args):
        entered.set()
        time.sleep(60)

    worker.run_tool = blocked_read
    with factory() as db:
        worker.run_once(db)
    engine.dispose()


def interrupted_write_worker(database_url: str, data_dir: str, written) -> None:
    from app import tool_runner, worker

    engine = make_engine(database_url)
    factory = sessionmaker(bind=engine)
    tool_runner.get_settings = lambda: SimpleNamespace(data_dir=data_dir)
    original = worker.run_tool

    def block_after_write(db, task, step):
        result = original(db, task, step)
        written.set()
        time.sleep(60)
        return result

    worker.run_tool = block_after_write
    with factory() as db:
        worker.run_once(db)
    engine.dispose()


def test_killed_worker_replays_expired_read_lease(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'crash.db'}"
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        task = Task(goal="Recover after process exit", state="queued", workspace_path=str(DEMO_WORKSPACE), capabilities_json='["read_file"]', input_files_json='["brief.md"]', plan_version=1)
        db.add(task)
        db.flush()
        step = PlanStep(task_id=task.id, ordinal=1, description="Read brief", tool_name="read_file", args_json='{"path":"brief.md"}', args_hash=args_hash({"path": "brief.md"}), risk_level="low", state="pending")
        db.add(step)
        db.flush()
        task_id, step_id = task.id, step.id
        db.commit()
    context = multiprocessing.get_context("spawn")
    entered = context.Event()
    process = context.Process(target=interrupted_read_worker, args=(database_url, entered))
    try:
        process.start()
        assert entered.wait(timeout=10), "Worker did not enter the read"
        process.terminate()
        process.join(timeout=5)
        assert not process.is_alive()
        with factory() as db:
            assert db.get(Task, task_id).state == "running"
            execution = db.scalar(select(Execution).where(Execution.step_id == step_id))
            assert execution.attempt == 1 and execution.status == "running"
            execution.lease_until = utc_now() - timedelta(seconds=1)
            db.commit()
        with factory() as db:
            assert run_once(db)
            assert db.get(Task, task_id).state == "completed"
            execution = db.scalar(select(Execution).where(Execution.step_id == step_id))
            assert execution.attempt == 2 and execution.status == "completed"
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        engine.dispose()


def test_killed_worker_does_not_repeat_uncertain_write(tmp_path, monkeypatch) -> None:
    from app import recovery

    database_url = f"sqlite:///{tmp_path / 'uncertain.db'}"
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    source = (DEMO_WORKSPACE / "brief.md").read_text(encoding="utf-8")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    with factory() as db:
        task = Task(goal="Recover uncertain write", state="running", workspace_path=str(DEMO_WORKSPACE), capabilities_json='["read_file","write_report"]', input_files_json='["brief.md"]', plan_version=1)
        db.add(task)
        db.flush()
        read = PlanStep(task_id=task.id, ordinal=1, description="Read brief", tool_name="read_file", args_json='{"path":"brief.md"}', args_hash=args_hash({"path": "brief.md"}), risk_level="low", state="completed")
        write = PlanStep(task_id=task.id, ordinal=2, description="Write report", tool_name="write_report", args_json='{"filename":"report.md"}', args_hash=args_hash({"filename": "report.md"}), risk_level="high", state="pending", dependencies_json="[1]")
        db.add_all([read, write])
        db.flush()
        db.add(Execution(step_id=read.id, attempt=1, idempotency_key=approval_scope(task, read), status="completed", result_json=json.dumps({"source": "brief.md", "content": source, "sha256": digest})))
        db.add(Approval(step_id=write.id, scope_hash=approval_scope(task, write), requested_action="Write report.md", decision="approved", expires_at=utc_now() + timedelta(hours=1)))
        task_id, write_id = task.id, write.id
        db.commit()
    context = multiprocessing.get_context("spawn")
    written = context.Event()
    process = context.Process(target=interrupted_write_worker, args=(database_url, str(tmp_path), written))
    report = tmp_path / "artifacts" / task_id / "report.md"
    try:
        process.start()
        assert written.wait(timeout=10), "Worker did not create the report"
        process.terminate()
        process.join(timeout=5)
        assert not process.is_alive() and report.is_file()
        with factory() as db:
            execution = db.scalar(select(Execution).where(Execution.step_id == write_id))
            assert execution.status == "running" and execution.attempt == 1
            assert db.scalar(select(func.count()).select_from(Artifact).where(Artifact.task_id == task_id)) == 0
            execution.lease_until = utc_now() - timedelta(seconds=1)
            db.commit()
        with factory() as db:
            assert run_once(db)
            assert db.get(Task, task_id).state == "failed"
            assert db.get(PlanStep, write_id).state == "needs_review"
            assert db.scalar(select(func.count()).select_from(Execution).where(Execution.step_id == write_id)) == 1
            assert not run_once(db)
        assert list(report.parent.iterdir()) == [report]
        monkeypatch.setattr(recovery, "get_settings", lambda: SimpleNamespace(data_dir=str(tmp_path)))
        with factory() as db:
            inspection = recovery.recovery_status(task_id, db)
            assert inspection["status"] == "matches"
        with factory() as db:
            resolved = recovery.resolve_recovery(task_id, recovery.RecoveryDecision(step_id=write_id, decision="accept_existing", expected_sha256=inspection["expected_sha256"]), db)
            assert resolved["task_state"] == "completed"
            assert db.scalar(select(func.count()).select_from(Artifact).where(Artifact.task_id == task_id)) == 1
        assert list(report.parent.iterdir()) == [report]
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        engine.dispose()


def test_two_processes_complete_queue_without_duplicate_executions(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'processes.db'}"
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    expected = 12
    with factory() as db:
        for number in range(expected):
            task = Task(goal=f"Read task {number}", state="queued", workspace_path=str(DEMO_WORKSPACE), capabilities_json=json.dumps(["read_file"]), input_files_json=json.dumps(["brief.md"]), plan_version=1)
            db.add(task)
            db.flush()
            db.add(PlanStep(task_id=task.id, ordinal=1, description="Read brief", tool_name="read_file", args_json=json.dumps({"path": "brief.md"}), args_hash=args_hash({"path": "brief.md"}), risk_level="low", state="pending"))
        db.commit()
    context = multiprocessing.get_context("spawn")
    gate = context.Event()
    processes = [context.Process(target=process_worker, args=(database_url, gate, expected)) for _ in range(2)]
    try:
        for process in processes:
            process.start()
        gate.set()
        for process in processes:
            process.join(timeout=12)
            assert process.exitcode == 0
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(Task).where(Task.state == "completed")) == expected
            assert db.scalar(select(func.count()).select_from(Execution)) == expected
            assert db.scalar(select(func.count()).select_from(Execution).where(Execution.attempt != 1)) == 0
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
        engine.dispose()
