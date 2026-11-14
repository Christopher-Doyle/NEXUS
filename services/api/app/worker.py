"""Single-machine durable worker. Run separately: python -m app.worker."""
import json
import time
from datetime import UTC, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import SessionLocal
from app.models import Approval, Execution, PlanStep, Task, utc_now
from app.state import transition
from app.tasks import record_event
from app.tool_policy import ToolDenied, approval_scope, validate_invocation
from app.tool_runner import run_tool


def run_once(db: Session) -> bool:
    task = db.scalar(select(Task).options(selectinload(Task.steps)).where(Task.state.in_(["queued", "running", "pausing"])).order_by(Task.created_at, Task.id))
    if task is None:
        return False
    if task.state == "pausing":
        transition(task, "paused")
        record_event(db, task.id, "task_state", {"state": task.state})
        db.commit()
        return True
    if task.state == "queued":
        transition(task, "running")
        record_event(db, task.id, "task_state", {"state": task.state})
        db.commit()
    steps = sorted(task.steps, key=lambda item: item.ordinal)
    if all(step.state == "completed" for step in steps):
        transition(task, "completed")
        record_event(db, task.id, "task_state", {"state": task.state})
        db.commit()
        return True
    step = next((item for item in steps if item.state in {"pending", "running"} and all(steps[number - 1].state == "completed" for number in json.loads(item.dependencies_json))), None)
    if step is None:
        return False
    try:
        validate_invocation(task, step)
    except ToolDenied as exc:
        step.state = "failed"
        transition(task, "failed")
        record_event(db, task.id, "tool_denied", {"step_id": step.id, "error": str(exc)})
        db.commit()
        return True
    execution = db.scalar(select(Execution).where(Execution.step_id == step.id))
    if step.state == "running" and execution is not None:
        if step.tool_name == "write_report":
            step.state = "needs_review"
            transition(task, "failed")
            execution.status = "needs_review"
            record_event(db, task.id, "execution_uncertain", {"step_id": step.id})
            db.commit()
            return True
        execution.attempt += 1
        execution.started_at = utc_now()
        execution.lease_until = utc_now() + timedelta(seconds=60)
        db.commit()
    else:
        if step.tool_name == "write_report":
            scope = approval_scope(task, step)
            approval = db.scalar(select(Approval).where(Approval.step_id == step.id, Approval.scope_hash == scope).order_by(Approval.created_at.desc()))
            if approval is None:
                db.add(Approval(step_id=step.id, scope_hash=scope, requested_action=f"Write report {json.loads(step.args_json)['filename']}", expires_at=utc_now() + timedelta(hours=1)))
                transition(task, "waiting_approval")
                record_event(db, task.id, "approval_requested", {"step_id": step.id})
                db.commit()
                return True
            expiry = approval.expires_at.replace(tzinfo=UTC) if approval.expires_at and approval.expires_at.tzinfo is None else approval.expires_at
            if expiry is not None and expiry <= utc_now():
                approval.decision = "expired"
                db.add(Approval(step_id=step.id, scope_hash=scope, requested_action=approval.requested_action, expires_at=utc_now() + timedelta(hours=1)))
                transition(task, "waiting_approval")
                record_event(db, task.id, "approval_requested", {"step_id": step.id})
                db.commit()
                return True
            if approval.decision != "approved":
                return False
        if step.tool_name not in json.loads(task.capabilities_json):
            step.state = "failed"
            transition(task, "failed")
            record_event(db, task.id, "tool_denied", {"step_id": step.id})
            db.commit()
            return True
        execution = Execution(step_id=step.id, attempt=1, idempotency_key=approval_scope(task, step), status="running", started_at=utc_now(), lease_until=utc_now() + timedelta(seconds=60))
        db.add(execution)
        step.state = "running"
        db.commit()
    try:
        result = run_tool(db, task, step)
        execution.result_json = json.dumps(result)
        execution.status = "completed"
        execution.ended_at = utc_now()
        step.state = "completed"
        record_event(db, task.id, "step_completed", {"step_id": step.id, "tool_name": step.tool_name, "result": {key: value for key, value in result.items() if key != "content"}})
        db.flush()
        db.refresh(task)
        if task.state == "pausing":
            transition(task, "paused")
            record_event(db, task.id, "task_state", {"state": task.state})
        elif task.state == "running" and all(item.state == "completed" for item in steps):
            transition(task, "completed")
            record_event(db, task.id, "task_state", {"state": task.state})
        db.commit()
    except (ToolDenied, OSError, UnicodeError) as exc:
        db.rollback()
        step = db.get(PlanStep, step.id)
        task = db.get(Task, task.id)
        execution = db.get(Execution, execution.id)
        step.state = "failed"
        execution.status = "failed"
        execution.error_code = type(exc).__name__
        execution.ended_at = utc_now()
        db.flush()
        db.refresh(task)
        if task.state in {"running", "pausing"}:
            transition(task, "failed")
        record_event(db, task.id, "step_failed", {"step_id": step.id, "error": str(exc)[:300]})
        db.commit()
    return True


def main() -> None:
    while True:
        with SessionLocal() as db:
            worked = run_once(db)
        if not worked:
            time.sleep(1)


if __name__ == "__main__":
    main()
