import asyncio
import hashlib
import json
import os
import stat
from datetime import UTC
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.contracts import ApprovalDecision, ApprovalView
from app.db import SessionLocal, begin_write, get_db
from app.models import Approval, Artifact, Event, Execution, PlanStep, Task, utc_now
from app.registry import REGISTRY
from app.state import deadline_expired, transition
from app.tasks import record_event
from app.tool_policy import approval_scope

router = APIRouter(prefix="/api/v1", tags=["operations"])
DbSession = Annotated[Session, Depends(get_db)]


def utc_iso(value) -> str:
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()


def approval_view(approval: Approval, task_id: str) -> ApprovalView:
    return ApprovalView(id=approval.id, task_id=task_id, step_id=approval.step_id, scope_hash=approval.scope_hash, requested_action=approval.requested_action, decision=approval.decision, expires_at=approval.expires_at)


@router.get("/approvals", response_model=list[ApprovalView])
def list_approvals(db: DbSession) -> list[ApprovalView]:
    rows = db.execute(select(Approval, PlanStep.task_id).join(PlanStep).join(Task, PlanStep.task_id == Task.id).where(Approval.decision == "pending", Task.state == "waiting_approval").order_by(Approval.created_at).limit(100)).all()
    return [approval_view(approval, task_id) for approval, task_id in rows]


@router.post("/approvals/{approval_id}/decision", response_model=ApprovalView)
def decide_approval(approval_id: str, body: ApprovalDecision, db: DbSession) -> ApprovalView:
    begin_write(db)
    approval = db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    step = db.get(PlanStep, approval.step_id)
    task = db.get(Task, step.task_id)
    if deadline_expired(task) and task.state == "waiting_approval":
        transition(task, "failed")
        record_event(db, task.id, "task_timeout", {"deadline_at": task.deadline_at.isoformat()})
        db.commit()
        raise HTTPException(status_code=409, detail="Task execution deadline expired")
    expiry = approval.expires_at.replace(tzinfo=UTC) if approval.expires_at and approval.expires_at.tzinfo is None else approval.expires_at
    if approval.decision != "pending" or task.state != "waiting_approval" or approval.scope_hash != body.scope_hash or approval.scope_hash != approval_scope(task, step) or (expiry is not None and expiry <= utc_now()):
        raise HTTPException(status_code=409, detail="Approval is stale, expired or already decided")
    approval.decision = body.decision
    approval.decided_at = utc_now()
    if body.decision == "approved":
        transition(task, "running")
    else:
        step.state = "rejected"
        transition(task, "failed")
    record_event(db, task.id, "approval_decided", {"step_id": step.id, "decision": body.decision})
    db.commit()
    return approval_view(approval, task.id)


@router.get("/tasks/{task_id}/events")
def task_events(task_id: str, db: DbSession, after: int = 0, last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None):
    if db.get(Task, task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if last_event_id is not None:
        try:
            after = int(last_event_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid event cursor") from exc
    if after < 0:
        raise HTTPException(status_code=422, detail="Invalid event cursor")

    async def stream():
        cursor = after
        while True:
            with SessionLocal() as session:
                rows = session.scalars(select(Event).where(Event.task_id == task_id, Event.seq > cursor).order_by(Event.seq).limit(100)).all()
            for event in rows:
                cursor = event.seq
                payload = {"id": event.seq, "type": event.kind, "occurred_at": utc_iso(event.created_at), "resource_id": task_id, "payload": json.loads(event.payload_json)}
                yield f"id: {event.seq}\nevent: update\ndata: {json.dumps(payload)}\n\n"
            if not rows:
                yield ": keepalive\n\n"
                await asyncio.sleep(2)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/tasks/{task_id}/journal")
def task_journal(task_id: str, db: DbSession) -> list[dict]:
    if db.get(Task, task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    rows = db.scalars(select(Event).where(Event.task_id == task_id).order_by(Event.seq).limit(500)).all()
    return [{"id": event.seq, "type": event.kind, "occurred_at": utc_iso(event.created_at), "payload": json.loads(event.payload_json)} for event in rows]


@router.get("/tasks/{task_id}/executions")
def task_executions(task_id: str, db: DbSession) -> list[dict]:
    if db.get(Task, task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    rows = db.execute(select(Execution, PlanStep).join(PlanStep, Execution.step_id == PlanStep.id).where(PlanStep.task_id == task_id).order_by(PlanStep.ordinal, Execution.attempt).limit(100)).all()
    receipts = []
    for execution, step in rows:
        result = None
        if execution.result_json:
            try:
                result = REGISTRY[step.tool_name].output.model_validate_json(execution.result_json).model_dump(exclude={"content"})
            except (KeyError, ValidationError):
                pass
        receipts.append({"id": execution.id, "step_id": step.id, "step_ordinal": step.ordinal, "tool_name": step.tool_name, "tool_version": execution.tool_version, "args_hash": step.args_hash, "idempotency_key": execution.idempotency_key, "attempt": execution.attempt, "status": execution.status, "started_at": utc_iso(execution.started_at) if execution.started_at else None, "ended_at": utc_iso(execution.ended_at) if execution.ended_at else None, "lease_until": utc_iso(execution.lease_until) if execution.lease_until else None, "error_code": execution.error_code, "result": result})
    return receipts


@router.get("/tasks/{task_id}/artifacts")
def task_artifacts(task_id: str, db: DbSession) -> list[dict]:
    if db.get(Task, task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    rows = db.scalars(select(Artifact).where(Artifact.task_id == task_id).order_by(Artifact.created_at)).all()
    return [{"id": item.id, "filename": Path(item.safe_path).name, "sha256": item.sha256, "size_bytes": item.size_bytes, "media_type": item.media_type, "created_at": utc_iso(item.created_at)} for item in rows]


@router.get("/artifacts")
def artifact_library(db: DbSession, limit: int = 20, offset: int = 0) -> dict:
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(status_code=422, detail="Invalid pagination")
    rows = db.execute(select(Artifact, Task.goal).join(Task, Artifact.task_id == Task.id).order_by(Artifact.created_at.desc(), Artifact.id.desc()).limit(limit).offset(offset)).all()
    total = db.scalar(select(func.count()).select_from(Artifact)) or 0
    return {"items": [{"id": item.id, "task_id": item.task_id, "task_goal": goal, "filename": Path(item.safe_path).name, "sha256": item.sha256, "size_bytes": item.size_bytes, "media_type": item.media_type, "created_at": utc_iso(item.created_at)} for item, goal in rows], "total": total}


@router.get("/artifacts/{artifact_id}")
def download_artifact(artifact_id: str, db: DbSession):
    artifact = db.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    root = Path(get_settings().data_dir).resolve() / "artifacts"
    if root.is_symlink() or (root.exists() and root.resolve() != root):
        raise HTTPException(status_code=404, detail="Artifact is unavailable")
    path = Path(artifact.safe_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact is unavailable")
    max_bytes = REGISTRY["write_report"].resource_limits["report_bytes"]
    try:
        expected = path.stat()
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            actual = os.fstat(stream.fileno())
            if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino) or not stat.S_ISREG(actual.st_mode):
                raise HTTPException(status_code=409, detail="Artifact changed before download")
            data = stream.read(max_bytes + 1)
    except OSError as exc:
        raise HTTPException(status_code=404, detail="Artifact is unavailable") from exc
    if len(data) > max_bytes or len(data) != artifact.size_bytes or hashlib.sha256(data).hexdigest() != artifact.sha256:
        raise HTTPException(status_code=409, detail="Artifact integrity check failed")
    return Response(data, media_type=artifact.media_type, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(path.name)}"})
