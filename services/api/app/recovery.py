"""Operator resolution for a report write interrupted after its lease expired."""

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import begin_write, get_db
from app.models import Artifact, Execution, PlanStep, Task, utc_now
from app.registry import WriteReportArgs, WriteReportResult
from app.tasks import record_event
from app.tool_policy import ToolDenied
from app.tool_runner import report_bytes

router = APIRouter(prefix="/api/v1", tags=["recovery"])
DbSession = Annotated[Session, Depends(get_db)]


class RecoveryDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_id: str
    decision: Literal["accept_existing", "confirm_absent"]
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def inspect_recovery(db: Session, task_id: str) -> tuple[Task, PlanStep, Execution, Path, bytes, dict]:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    step = db.scalar(select(PlanStep).where(PlanStep.task_id == task_id, PlanStep.tool_name == "write_report", PlanStep.state == "needs_review"))
    if task.state != "failed" or step is None:
        raise HTTPException(status_code=409, detail="No uncertain report write requires review")
    execution = db.scalar(select(Execution).where(Execution.step_id == step.id, Execution.status == "needs_review"))
    if execution is None:
        raise HTTPException(status_code=409, detail="Uncertain execution record is unavailable")
    try:
        filename = WriteReportArgs.model_validate_json(step.args_json).filename
        expected = report_bytes(db, task)
    except (ValidationError, ToolDenied, KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail="Source evidence cannot be verified") from exc
    data_root = Path(get_settings().data_dir).resolve()
    artifact_root = data_root / "artifacts"
    task_root = artifact_root / task.id
    target = task_root / filename
    expected_sha = hashlib.sha256(expected).hexdigest()
    status = "absent"
    actual_sha = None
    if any(path.is_symlink() or (path.exists() and path.resolve() != path) for path in (artifact_root, task_root, target)):
        status = "unsafe"
    elif target.exists():
        if not target.is_file() or target.stat().st_size > len(expected):
            status = "unsafe"
        else:
            actual_sha = hashlib.sha256(target.read_bytes()).hexdigest()
            status = "matches" if actual_sha == expected_sha else "mismatch"
    snapshot = {"step_id": step.id, "filename": filename, "status": status, "expected_sha256": expected_sha, "actual_sha256": actual_sha}
    return task, step, execution, target, expected, snapshot


@router.get("/tasks/{task_id}/recovery")
def recovery_status(task_id: str, db: DbSession) -> dict:
    return inspect_recovery(db, task_id)[5]


@router.post("/tasks/{task_id}/recovery")
def resolve_recovery(task_id: str, body: RecoveryDecision, db: DbSession) -> dict:
    begin_write(db)
    task, step, execution, target, expected, snapshot = inspect_recovery(db, task_id)
    if body.step_id != step.id or body.expected_sha256 != snapshot["expected_sha256"]:
        raise HTTPException(status_code=409, detail="Recovery inspection is stale")
    if body.decision == "accept_existing":
        if snapshot["status"] != "matches" or db.scalar(select(Artifact).where(Artifact.task_id == task.id, Artifact.safe_path == str(target))):
            raise HTTPException(status_code=409, detail="Report file is not safe to accept")
        artifact = Artifact(task_id=task.id, safe_path=str(target), sha256=snapshot["expected_sha256"], media_type="text/markdown", size_bytes=len(expected))
        db.add(artifact)
        db.flush()
        execution.result_json = json.dumps(WriteReportResult(artifact_id=artifact.id, filename=target.name, sha256=artifact.sha256).model_dump())
        execution.status = "completed"
        step.state = "completed"
        if all(item.state == "completed" for item in db.scalars(select(PlanStep).where(PlanStep.task_id == task.id))):
            task.state = "completed"
            task.updated_at = utc_now()
            task.completed_at = task.updated_at
    elif snapshot["status"] == "absent":
        execution.status = "failed"
        execution.error_code = "ConfirmedAbsent"
        step.state = "failed"
    else:
        raise HTTPException(status_code=409, detail="Report file is present or unsafe")
    execution.ended_at = utc_now()
    record_event(db, task.id, "recovery_resolved", {"step_id": step.id, "decision": body.decision, "sha256": snapshot["expected_sha256"]})
    db.commit()
    return {"task_state": task.state, "step_state": step.state, "decision": body.decision}
