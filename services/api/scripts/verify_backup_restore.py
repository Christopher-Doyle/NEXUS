"""Exercise the stopped-service local backup and restore runbook in isolation."""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine
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

        from app.models import Artifact, Task

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
            session.commit()
            task_id, artifact_id = task.id, artifact.id
        engine.dispose()

        backup = root / "backup"
        shutil.copytree(data, backup)
        shutil.rmtree(data)
        shutil.copytree(backup, data)
        migrate(environment)

        from app.config import get_settings
        from app.operations import download_artifact

        get_settings.cache_clear()
        os.environ["DATABASE_URL"] = environment["DATABASE_URL"]
        os.environ["DATA_DIR"] = str(data)
        restored = create_engine(environment["DATABASE_URL"])
        try:
            with Session(restored) as session:
                assert session.get(Task, task_id) is not None
                response = download_artifact(artifact_id, session)
                assert response.body == contents
        finally:
            restored.dispose()
        print("Isolated database and verified artifact backup/restore passed")


if __name__ == "__main__":
    main()
