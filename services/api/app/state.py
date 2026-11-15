from datetime import UTC, datetime

from app.models import Task, utc_now

TRANSITIONS = {
    "draft": {"planning", "cancelled"},
    "planning": {"review_required", "failed", "cancelled"},
    "review_required": {"planning", "queued", "cancelled"},
    "queued": {"running", "failed", "cancelled"},
    "running": {"waiting_approval", "pausing", "failed", "cancelled", "completed"},
    "waiting_approval": {"running", "failed", "cancelled"},
    "pausing": {"paused", "failed", "cancelled"},
    "paused": {"queued", "failed", "cancelled"},
    "failed": set(),
    "cancelled": set(),
    "completed": set(),
}


def deadline_expired(task: Task, now: datetime | None = None) -> bool:
    if task.deadline_at is None:
        return False
    deadline = task.deadline_at.replace(tzinfo=UTC) if task.deadline_at.tzinfo is None else task.deadline_at
    return deadline <= (now or utc_now())


def transition(task: Task, target: str) -> None:
    if target not in TRANSITIONS.get(task.state, set()):
        raise ValueError(f"Cannot transition from {task.state} to {target}")
    task.state = target
    task.updated_at = utc_now()
    if target in {"failed", "cancelled", "completed"}:
        task.completed_at = task.updated_at
