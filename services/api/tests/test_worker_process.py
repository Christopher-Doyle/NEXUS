import json
import multiprocessing
import time

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.models import Execution, PlanStep, Task
from app.planning import args_hash
from app.tasks import DEMO_WORKSPACE
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
