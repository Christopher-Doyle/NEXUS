"""Delete only files owned by a task under the configured app data root."""

import shutil
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Approval, Artifact, Event, Execution, PlanStep, Task


class RetentionError(Exception):
    pass


def task_owned_dir(data_root: Path, kind: str, task_id: str) -> Path:
    parent = data_root / kind
    if parent.is_symlink() or (parent.exists() and parent.resolve() != parent):
        raise RetentionError(f"{kind} directory is redirected")
    target = parent / task_id
    if target.is_symlink() or (target.exists() and target.resolve() != target):
        raise RetentionError(f"Task {kind} directory is redirected")
    return target


def delete_task(db: Session, task: Task, data_dir: str) -> None:
    data_root = Path(data_dir).resolve()
    trash = data_root / "deleting"
    trash.mkdir(parents=True, exist_ok=True)
    if trash.resolve() != trash:
        raise RetentionError("Deletion staging directory is redirected")
    stage = trash / task.id
    if stage.exists() or stage.is_symlink():
        raise RetentionError("A prior deletion for this task needs operator review")
    sources = [(kind, task_owned_dir(data_root, kind, task.id)) for kind in ("inputs", "workspaces", "artifacts")]
    stage.mkdir()
    moved: list[tuple[Path, Path]] = []
    try:
        for kind, source in sources:
            if source.exists():
                destination = stage / kind
                source.rename(destination)
                moved.append((source, destination))
        step_ids = select(PlanStep.id).where(PlanStep.task_id == task.id)
        db.execute(delete(Approval).where(Approval.step_id.in_(step_ids)))
        db.execute(delete(Execution).where(Execution.step_id.in_(step_ids)))
        db.execute(delete(PlanStep).where(PlanStep.task_id == task.id))
        db.execute(delete(Event).where(Event.task_id == task.id))
        db.execute(delete(Artifact).where(Artifact.task_id == task.id))
        db.execute(delete(Task).where(Task.id == task.id))
        db.commit()
    except Exception:
        db.rollback()
        for source, destination in reversed(moved):
            destination.rename(source)
        stage.rmdir()
        raise
    try:
        shutil.rmtree(stage)
    except OSError as exc:
        raise RetentionError("Task records were deleted but staged files need operator cleanup") from exc
