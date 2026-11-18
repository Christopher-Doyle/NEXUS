"""Exercise the stopped-service local backup and restore runbook in isolation."""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


def migrate(environment: dict[str, str]) -> None:
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=environment, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"Migration failed during backup verification:\n{result.stdout}{result.stderr}")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="nexus-backup-") as temporary:
        root = Path(temporary)
        data = root / "data"
        data.mkdir()
        database = data / "nexus.db"
        environment = os.environ.copy()
        environment["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
        environment["DATA_DIR"] = str(data)
        migrate(environment)

        from app.models import Artifact, Execution, PlanStep, Task, utc_now
        from app.planning import args_hash
        from app.tool_policy import approval_scope

        engine = create_engine(environment["DATABASE_URL"])
        contents = b"# Verified local backup fixture\n"
        with Session(engine) as session:
            task = Task(goal="Verify a local backup", state="completed")
            session.add(task)
            session.flush()
            report = data / "artifacts" / task.id / "report.md"
            report.parent.mkdir(parents=True)
            report.write_bytes(contents)
            artifact = Artifact(task_id=task.id, safe_path=str(report), sha256=hashlib.sha256(contents).hexdigest(), size_bytes=len(contents), media_type="text/markdown")
            session.add(artifact)
            interrupted = Task(goal="Resume a restored read", state="running", capabilities_json='["read_file"]', input_files_json='["note.md"]', plan_version=1)
            session.add(interrupted)
            session.flush()
            workspace = data / "workspaces" / interrupted.id
            workspace.mkdir(parents=True)
            (workspace / "note.md").write_text("Restored local note.\n", encoding="utf-8")
            interrupted.workspace_path = str(workspace)
            step = PlanStep(task_id=interrupted.id, ordinal=1, description="Read restored note", tool_name="read_file", args_json='{"path":"note.md"}', args_hash=args_hash({"path": "note.md"}), risk_level="low", state="running")
            session.add(step)
            session.flush()
            session.add(Execution(step_id=step.id, attempt=1, idempotency_key=approval_scope(interrupted, step), status="running", started_at=utc_now() - timedelta(minutes=2), lease_until=utc_now() - timedelta(minutes=1)))
            session.commit()
            task_id, artifact_id = task.id, artifact.id
            interrupted_id, step_id = interrupted.id, step.id
        engine.dispose()

        backup = root / "backup"
        shutil.copytree(data, backup)
        shutil.rmtree(data)
        shutil.copytree(backup, data)
        migrate(environment)

        from app.config import get_settings
        from app.operations import download_artifact
        from app.worker import run_once

        get_settings.cache_clear()
        os.environ["DATABASE_URL"] = environment["DATABASE_URL"]
        os.environ["DATA_DIR"] = str(data)
        restored = create_engine(environment["DATABASE_URL"])
        try:
            with Session(restored) as session:
                assert session.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"
                assert session.execute(text("PRAGMA foreign_key_check")).all() == []
                assert session.get(Task, task_id) is not None
                response = download_artifact(artifact_id, session)
                assert response.body == contents
                assert run_once(session)
                assert session.get(Task, interrupted_id).state == "completed"
                restored_step = session.get(PlanStep, step_id)
                assert restored_step.state == "completed"
                execution = session.query(Execution).filter_by(step_id=step_id).one()
                assert execution.attempt == 2 and execution.status == "completed"
        finally:
            restored.dispose()
        print("Isolated database, verified artifact and interrupted read backup/restore passed")


if __name__ == "__main__":
    main()
