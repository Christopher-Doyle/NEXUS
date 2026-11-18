"""Check that the previous supported database schema upgrades without losing receipts."""

import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]


def test_prior_schema_preserves_execution_receipt(tmp_path: Path) -> None:
    database = tmp_path / "prior.db"
    environment = {**os.environ, "DATABASE_URL": f"sqlite:///{database.as_posix()}", "DATA_DIR": str(tmp_path)}

    def upgrade(revision: str) -> None:
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", revision], cwd=API_ROOT, env=environment, check=True, capture_output=True, text=True)

    upgrade("a721d11d5509")
    with sqlite3.connect(database) as connection:
        now = datetime.now(UTC).isoformat()
        connection.execute("INSERT INTO task (id, goal, constraints_json, state, plan_version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", ("task-1", "Retain prior receipt", "[]", "completed", 1, now, now))
        connection.execute("INSERT INTO plan_step (id, task_id, ordinal, description, tool_name, args_json, args_hash, risk_level, state, dependencies_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("step-1", "task-1", 1, "Read note", "read_file", '{"path":"note.md"}', "a" * 64, "low", "completed", "[]", now, now))
        connection.execute("INSERT INTO execution (id, step_id, attempt, idempotency_key, status, result_json) VALUES (?, ?, ?, ?, ?, ?)", ("execution-1", "step-1", 1, "b" * 64, "completed", '{"source":"note.md"}'))
    upgrade("head")
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT tool_version, status, result_json FROM execution WHERE id = 'execution-1'").fetchone() == ("1", "completed", '{"source":"note.md"}')
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("f6a916c64f20",)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
