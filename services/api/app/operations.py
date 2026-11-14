import asyncio
import hashlib
import json
from datetime import UTC
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.contracts import ApprovalDecision, ApprovalView
from app.db import SessionLocal, get_db
from app.models import Approval, Artifact, Event, PlanStep, Task, utc_now
from app.state import transition
from app.tasks import record_event
from app.tool_policy import approval_scope

router = APIRouter(prefix="/api/v1", tags=["operations"])
DbSession = Annotated[Session, Depends(get_db)]


def approval_view(approval: Approval, task_id: str) -> ApprovalView:
    return ApprovalView(id=approval.id, task_id=task_id, step_id=approval.step_id, scope_hash=approval.scope_hash, requested_action=approval.requested_action, decision=approval.decision, expires_at=approval.expires_at)


@router.get("/approvals", response_model=list[ApprovalView])
def list_approvals(db: DbSession) -> list[ApprovalView]:
    rows = db.execute(select(Approval, PlanStep.task_id).join(PlanStep).join(Task, PlanStep.task_id == Task.id).where(Approval.decision == "pending", Task.state == "waiting_approval").order_by(Approval.created_at).limit(100)).all()
    return [approval_view(approval, task_id) for approval, task_id in rows]


@router.post("/approvals/{approval_id}/decision", response_model=ApprovalView)
def decide_approval(approval_id: str, body: ApprovalDecision, db: DbSession) -> ApprovalView:
    approval = db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    step = db.get(PlanStep, approval.step_id)
    task = db.get(Task, step.task_id)
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
                payload = {"id": event.seq, "type": event.kind, "occurred_at": event.created_at.isoformat(), "resource_id": task_id, "payload": json.loads(event.payload_json)}
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
    return [{"id": event.seq, "type": event.kind, "occurred_at": event.created_at, "payload": json.loads(event.payload_json)} for event in rows]


@router.get("/tasks/{task_id}/artifacts")
def task_artifacts(task_id: str, db: DbSession) -> list[dict]:
    if db.get(Task, task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    rows = db.scalars(select(Artifact).where(Artifact.task_id == task_id).order_by(Artifact.created_at)).all()
    return [{"id": item.id, "filename": Path(item.safe_path).name, "sha256": item.sha256, "size_bytes": item.size_bytes, "media_type": item.media_type, "created_at": item.created_at} for item in rows]


@router.get("/artifacts/{artifact_id}")
def download_artifact(artifact_id: str, db: DbSession):
    artifact = db.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    root = (Path(get_settings().data_dir).resolve() / "artifacts").resolve()
    path = Path(artifact.safe_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact is unavailable")
    if hashlib.sha256(path.read_bytes()).hexdigest() != artifact.sha256:
        raise HTTPException(status_code=409, detail="Artifact integrity check failed")
    return FileResponse(path, media_type=artifact.media_type, filename=path.name)
