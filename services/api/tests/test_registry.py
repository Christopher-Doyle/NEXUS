import json

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.models import Event, Execution, PlanStep, Task
from app.planning import args_hash
from app.registry import REGISTRY
from app.tasks import DEMO_WORKSPACE
from app.worker import run_once


def test_every_registered_tool_declares_a_bounded_contract() -> None:
    assert set(REGISTRY) == {"read_file", "search_local_docs", "write_report", "fetch_url"}
    for name, spec in REGISTRY.items():
        assert spec.name == spec.capability == name
        assert spec.version and spec.description
        assert spec.timeout_seconds > 0
        assert spec.max_attempts > 0
        assert spec.max_output_bytes > 0
        assert spec.resource_limits and all(value > 0 for value in spec.resource_limits.values())
        assert spec.parameters.model_config["extra"] == "forbid"
        assert spec.output.model_config["extra"] == "forbid"
    assert REGISTRY["write_report"].risk == "high"
    assert REGISTRY["write_report"].retry == "manual_review"
    assert REGISTRY["write_report"].max_attempts == 1
    assert REGISTRY["read_file"].max_attempts == 3
    assert REGISTRY["write_report"].idempotency == "exclusive_create"
    assert REGISTRY["fetch_url"].risk == "high"
    assert REGISTRY["fetch_url"].retry == "manual_review"
    assert REGISTRY["fetch_url"].idempotency == "uncertain_external"


def test_search_output_rejects_extra_fields_and_unbounded_matches() -> None:
    schema = REGISTRY["search_local_docs"].output
    with pytest.raises(ValidationError):
        schema.model_validate({"query": "Atlas", "matches": [], "truncated": False, "ignored": True})
    with pytest.raises(ValidationError):
        schema.model_validate({"query": "Atlas", "matches": [{"source": "a.md", "line": 1, "excerpt": "x"}] * 21, "truncated": True})


def test_worker_rejects_tool_output_that_breaks_registry_schema(tmp_path, monkeypatch) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'invalid-output.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        task = Task(goal="Read invalid output", state="queued", workspace_path=str(DEMO_WORKSPACE), capabilities_json='["read_file"]', input_files_json='["brief.md"]', plan_version=1)
        db.add(task)
        db.flush()
        step = PlanStep(task_id=task.id, ordinal=1, description="Read brief", tool_name="read_file", args_json='{"path":"brief.md"}', args_hash=args_hash({"path": "brief.md"}), risk_level="low", state="pending")
        db.add(step)
        db.commit()
    monkeypatch.setattr("app.worker.run_tool", lambda *_: {"unregistered": "output"})
    with factory() as db:
        assert run_once(db)
        assert db.get(Task, task.id).state == "failed"
        assert db.get(PlanStep, step.id).state == "failed"
        assert db.query(Execution).filter_by(step_id=step.id).one().error_code == "ToolDenied"
    engine.dispose()


def test_journal_redacts_filesystem_exception_details(tmp_path, monkeypatch) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'filesystem-error.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        task = Task(goal="Read a missing file", state="queued", workspace_path=str(DEMO_WORKSPACE), capabilities_json='["read_file"]', input_files_json='["brief.md"]', plan_version=1)
        db.add(task)
        db.flush()
        step = PlanStep(task_id=task.id, ordinal=1, description="Read brief", tool_name="read_file", args_json='{"path":"brief.md"}', args_hash=args_hash({"path": "brief.md"}), risk_level="low", state="pending")
        db.add(step)
        db.commit()
    monkeypatch.setattr("app.worker.run_tool", lambda *_: (_ for _ in ()).throw(OSError("C:/private/secret.txt")))
    with factory() as db:
        assert run_once(db)
        event = db.query(Event).filter_by(task_id=task.id, kind="step_failed").one()
        payload = json.loads(event.payload_json)
        assert payload["error"] == "Tool failed while accessing a local file"
        assert "secret" not in event.payload_json
    engine.dispose()
