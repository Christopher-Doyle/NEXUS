"""Single-machine durable worker. Run separately: python -m app.worker."""
import json
import multiprocessing
import time
from collections.abc import Callable
from datetime import UTC, timedelta
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import and_, case, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db import SessionLocal, begin_write
from app.models import Approval, Execution, PlanStep, Task, WorkerHeartbeat, utc_now
from app.preferences import effective_settings
from app.registry import REGISTRY
from app.retention import RetentionError, prune_old_tasks
from app.state import deadline_expired, transition
from app.tasks import record_event
from app.tool_policy import ToolDenied, approval_scope, validate_invocation
from app.tool_runner import run_tool


def run_once(db: Session, tool_start: Callable[[str, str], None] | None = None) -> bool:
    begin_write(db)
    expired = and_(Task.deadline_at.is_not(None), Task.deadline_at <= utc_now())
    task = db.scalar(select(Task).options(selectinload(Task.steps)).where(or_(Task.state.in_(["queued", "running", "pausing"]), and_(Task.state.in_(["waiting_approval", "paused"]), expired))).order_by(case((expired, 0), (Task.state == "pausing", 1), (Task.state == "queued", 2), else_=3), Task.created_at, Task.id))
    if task is None:
        db.commit()
        return False
    if deadline_expired(task):
        transition(task, "failed")
        record_event(db, task.id, "task_timeout", {"deadline_at": task.deadline_at.isoformat()})
        db.commit()
        return True
    if task.state == "pausing":
        transition(task, "paused")
        record_event(db, task.id, "task_state", {"state": task.state})
        db.commit()
        return True
    if task.state == "queued":
        transition(task, "running")
        record_event(db, task.id, "task_state", {"state": task.state})
    steps = sorted(task.steps, key=lambda item: item.ordinal)
    if all(step.state == "completed" for step in steps):
        transition(task, "completed")
        record_event(db, task.id, "task_state", {"state": task.state})
        db.commit()
        return True
    step = next((item for item in steps if item.state in {"pending", "running"} and all(steps[number - 1].state == "completed" for number in json.loads(item.dependencies_json))), None)
    if step is None:
        db.commit()
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
        lease = execution.lease_until.replace(tzinfo=UTC) if execution.lease_until and execution.lease_until.tzinfo is None else execution.lease_until
        if lease is not None and lease > utc_now():
            db.commit()
            return False
        if REGISTRY[step.tool_name].retry == "manual_review":
            step.state = "needs_review"
            transition(task, "failed")
            execution.status = "needs_review"
            record_event(db, task.id, "execution_uncertain", {"step_id": step.id})
            db.commit()
            return True
        if execution.attempt >= REGISTRY[step.tool_name].max_attempts:
            step.state = "failed"
            execution.status = "failed"
            execution.error_code = "RetryExhausted"
            execution.ended_at = utc_now()
            transition(task, "failed")
            record_event(db, task.id, "execution_retry_exhausted", {"step_id": step.id, "attempts": execution.attempt})
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
        execution = Execution(step_id=step.id, tool_version=REGISTRY[step.tool_name].version, attempt=1, idempotency_key=approval_scope(task, step), status="running", started_at=utc_now(), lease_until=utc_now() + timedelta(seconds=60))
        db.add(execution)
        step.state = "running"
        db.commit()
    if step.tool_name == "write_report":
        begin_write(db)
        db.refresh(task)
        if task.state == "cancelled":
            step.state = "cancelled"
            execution.status = "cancelled"
            execution.ended_at = utc_now()
            record_event(db, task.id, "step_cancelled", {"step_id": step.id})
            db.commit()
            return True
        if task.state == "pausing":
            step.state = "pending"
            db.delete(execution)
            transition(task, "paused")
            record_event(db, task.id, "task_state", {"state": task.state})
            db.commit()
            return True
        scope = approval_scope(task, step)
        approval = db.scalar(select(Approval).where(Approval.step_id == step.id, Approval.scope_hash == scope, Approval.decision == "approved").order_by(Approval.created_at.desc()))
        expiry = approval.expires_at.replace(tzinfo=UTC) if approval and approval.expires_at and approval.expires_at.tzinfo is None else approval.expires_at if approval else None
        if task.state != "running" or deadline_expired(task) or approval is None or (expiry is not None and expiry <= utc_now()):
            step.state = "failed"
            execution.status = "failed"
            execution.error_code = "ApprovalInvalid"
            execution.ended_at = utc_now()
            if task.state == "running":
                transition(task, "failed")
            record_event(db, task.id, "tool_denied", {"step_id": step.id, "error": "Approval or task deadline is no longer valid"})
            db.commit()
            return True
    try:
        spec = REGISTRY[step.tool_name]
        if tool_start is not None:
            tool_start(step.id, step.tool_name)
        try:
            result = spec.output.model_validate(run_tool(db, task, step)).model_dump()
        except ValidationError as exc:
            raise ToolDenied("Tool output failed schema validation") from exc
        result_json = json.dumps(result)
        if len(result_json.encode("utf-8")) > spec.max_output_bytes:
            raise ToolDenied("Tool output exceeds its registered limit")
        execution.result_json = result_json
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
        step.state = "needs_review" if step.tool_name == "write_report" else "failed"
        execution.status = step.state
        execution.error_code = type(exc).__name__
        execution.ended_at = utc_now()
        db.flush()
        db.refresh(task)
        if task.state in {"running", "pausing"}:
            transition(task, "failed")
        public_error = str(exc)[:300] if isinstance(exc, ToolDenied) else "Tool failed while accessing a local file"
        record_event(db, task.id, "step_failed", {"step_id": step.id, "error": public_error})
        db.commit()
    return True


def _run_once_process(sender) -> None:
    try:
        with SessionLocal() as db:
            worked = run_once(db, lambda step_id, name: sender.send(("started", step_id, name)))
        sender.send(("done", worked))
    except Exception as exc:  # noqa: BLE001 - isolate unexpected child failures
        sender.send(("error", type(exc).__name__))
    finally:
        sender.close()


def _record_tool_timeout(step_id: str, tool_name: str) -> None:
    with SessionLocal() as db:
        begin_write(db)
        step = db.get(PlanStep, step_id)
        if step is None or step.state != "running":
            db.commit()
            return
        execution = db.scalar(select(Execution).where(Execution.step_id == step_id, Execution.status == "running"))
        if execution is None:
            db.commit()
            return
        task = db.get(Task, step.task_id)
        review = REGISTRY[tool_name].retry == "manual_review"
        step.state = "needs_review" if review else "failed"
        execution.status = step.state
        execution.error_code = "ToolTimeout"
        execution.ended_at = utc_now()
        if task.state in {"running", "pausing"}:
            transition(task, "failed")
        record_event(db, task.id, "tool_timeout", {"step_id": step.id, "tool_name": tool_name, "timeout_seconds": REGISTRY[tool_name].timeout_seconds, "needs_review": review})
        db.commit()


def run_once_bounded(child_target=None) -> bool:
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=child_target or _run_once_process, args=(sender,))
    process.start()
    sender.close()
    started: tuple[str, str] | None = None
    deadline = time.monotonic() + 30
    worked = False
    try:
        while process.is_alive():
            try:
                available = receiver.poll(0.05)
            except (BrokenPipeError, OSError):
                available = False
            if available:
                try:
                    message = receiver.recv()
                except EOFError:
                    break
                if message[0] == "started":
                    started = (message[1], message[2])
                    deadline = time.monotonic() + REGISTRY[message[2]].timeout_seconds
                elif message[0] == "done":
                    worked = message[1]
                elif message[0] == "error":
                    print(f"Worker action failed: {message[1]}")
            if time.monotonic() >= deadline:
                process.terminate()
                process.join(timeout=2)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=2)
                if process.is_alive():
                    raise RuntimeError("Tool child could not be terminated")
                if started is not None:
                    _record_tool_timeout(*started)
                    return True
                return False
        process.join()
        while True:
            try:
                available = receiver.poll()
            except (BrokenPipeError, OSError):
                break
            if not available:
                break
            try:
                message = receiver.recv()
            except EOFError:
                break
            if message[0] == "done":
                worked = message[1]
            elif message[0] == "error":
                print(f"Worker action failed: {message[1]}")
        return worked
    finally:
        receiver.close()
        if process.is_alive():
            process.kill()
            process.join(timeout=2)
        if process.is_alive():
            raise RuntimeError("Tool child could not be terminated")


def main() -> None:
    worker_id = str(uuid4())
    last_prune = 0.0
    while True:
        with SessionLocal() as db:
            heartbeat = db.get(WorkerHeartbeat, worker_id)
            if heartbeat is None:
                heartbeat = WorkerHeartbeat(id=worker_id, started_at=utc_now(), last_seen_at=utc_now())
                db.add(heartbeat)
            else:
                heartbeat.last_seen_at = utc_now()
            db.commit()
            if time.monotonic() - last_prune >= 3600:
                try:
                    days = effective_settings(db).retention_days
                    db.commit()
                    prune_old_tasks(db, get_settings().data_dir, days)
                    last_prune = time.monotonic()
                except (OSError, RetentionError, SQLAlchemyError, ValueError):
                    db.rollback()
                    print("Retention cleanup needs operator review")
                    last_prune = time.monotonic() - 3540
            expired = and_(Task.deadline_at.is_not(None), Task.deadline_at <= utc_now())
            pending = db.scalar(select(Task.id).where(or_(Task.state.in_(["queued", "running", "pausing"]), and_(Task.state.in_(["waiting_approval", "paused"]), expired))).limit(1)) is not None
        if not pending:
            time.sleep(1)
            continue
        worked = run_once_bounded()
        if not worked:
            time.sleep(1)


if __name__ == "__main__":
    main()
