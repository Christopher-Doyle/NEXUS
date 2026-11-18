"""Measure a bounded queue of synthetic reads through the production worker."""

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import make_engine
from app.models import Execution, PlanStep, Task
from app.planning import args_hash
from app.tasks import DEMO_WORKSPACE

API_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=int, default=40, help="number of synthetic reads, 1–200")
    options = parser.parse_args()
    if not 1 <= options.tasks <= 200:
        parser.error("--tasks must be between 1 and 200")

    with tempfile.TemporaryDirectory(prefix="nexus-worker-load-") as temporary:
        root = Path(temporary)
        database = root / "nexus.db"
        url = f"sqlite:///{database.as_posix()}"
        environment = {**os.environ, "DATABASE_URL": url, "DATA_DIR": str(root), "OLLAMA_MODEL": "", "APPROVED_WORKSPACES": ""}
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=API_ROOT, env=environment, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        engine = make_engine(url)
        with Session(engine) as db:
            for number in range(options.tasks):
                task = Task(goal=f"Synthetic worker load {number + 1}", state="queued", workspace_path=str(DEMO_WORKSPACE), capabilities_json='["read_file"]', input_files_json='["brief.md"]', plan_version=1)
                db.add(task)
                db.flush()
                db.add(PlanStep(task_id=task.id, ordinal=1, description="Read synthetic note", tool_name="read_file", args_json='{"path":"brief.md"}', args_hash=args_hash({"path": "brief.md"}), risk_level="low", state="pending"))
            db.commit()

        started = time.monotonic()
        worker = subprocess.Popen([sys.executable, "-m", "app.worker"], cwd=API_ROOT, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = started + 120
            while time.monotonic() < deadline:
                if worker.poll() is not None:
                    raise RuntimeError(f"Worker exited with code {worker.returncode}")
                with Session(engine) as db:
                    completed = db.scalar(select(func.count()).select_from(Task).where(Task.state == "completed")) or 0
                    failed = db.scalar(select(func.count()).select_from(Task).where(Task.state == "failed")) or 0
                if failed:
                    raise RuntimeError(f"{failed} synthetic tasks failed")
                if completed == options.tasks:
                    break
                time.sleep(0.2)
            else:
                raise RuntimeError(f"Worker completed {completed}/{options.tasks} tasks before 120-second bound")
            elapsed = time.monotonic() - started
            with Session(engine) as db:
                receipts = db.scalars(select(Execution)).all()
                assert len(receipts) == options.tasks
                assert all(item.status == "completed" and item.attempt == 1 for item in receipts)
                assert db.scalar(select(func.count()).select_from(PlanStep).where(PlanStep.state != "completed")) == 0
            print(json.dumps({"platform": platform.platform(), "python": platform.python_version(), "tasks": options.tasks, "completed": completed, "single_attempt_receipts": len(receipts), "seconds": round(elapsed, 2), "tasks_per_second": round(options.tasks / elapsed, 2)}, indent=2))
        finally:
            worker.terminate()
            try:
                worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=5)
            engine.dispose()
            # A just-finished Windows spawn may still be closing its SQLite handle.
            time.sleep(2)


if __name__ == "__main__":
    main()
