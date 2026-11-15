import json
import os
from datetime import UTC, timedelta
from itertools import islice
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.contracts import PlanEdit, PlanRequest, StepInput, StepView, TaskCreate, TaskList, TaskView
from app.db import begin_write, get_db
from app.models import Approval, Event, PlanStep, Task, new_id, utc_now
from app.ollama import ModelPlanInvalid, ModelUnavailable, generate_plan
from app.planning import args_hash, demo_plan, validate_steps
from app.registry import REGISTRY
from app.state import TRANSITIONS, transition
from app.tool_policy import ToolDenied, workspace_file

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
DbSession = Annotated[Session, Depends(get_db)]
DEMO_WORKSPACE = Path(__file__).resolve().parents[3] / "fixtures" / "demo"


def task_view(task: Task) -> TaskView:
    return TaskView(
        id=task.id,
        goal=task.goal,
        constraints=json.loads(task.constraints_json),
        success_criteria=task.success_criteria,
        capabilities=json.loads(task.capabilities_json),
        network_access=task.network_access,
        workspace_path=task.workspace_path,
        input_files=json.loads(task.input_files_json),
        state=task.state,
        plan_version=task.plan_version,
        created_at=task.created_at.replace(tzinfo=UTC) if task.created_at.tzinfo is None else task.created_at,
        updated_at=task.updated_at.replace(tzinfo=UTC) if task.updated_at.tzinfo is None else task.updated_at,
        completed_at=(task.completed_at.replace(tzinfo=UTC) if task.completed_at.tzinfo is None else task.completed_at) if task.completed_at else None,
        deadline_at=(task.deadline_at.replace(tzinfo=UTC) if task.deadline_at.tzinfo is None else task.deadline_at) if task.deadline_at else None,
        steps=[StepView(
            id=step.id, ordinal=step.ordinal, description=step.description,
            tool_name=step.tool_name, args=json.loads(step.args_json), args_hash=step.args_hash,
            risk_level=step.risk_level, state=step.state,
            dependencies=json.loads(step.dependencies_json),
        ) for step in sorted(task.steps, key=lambda item: item.ordinal)],
    )


def get_task(db: Session, task_id: str) -> Task:
    task = db.scalar(select(Task).options(selectinload(Task.steps)).where(Task.id == task_id))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def record_event(db: Session, task_id: str, kind: str, payload: dict) -> None:
    db.add(Event(task_id=task_id, kind=kind, payload_json=json.dumps(payload), correlation_id=str(uuid4())))


def replace_steps(db: Session, task: Task, steps: list[StepInput]) -> None:
    old_ids = [step.id for step in task.steps]
    if old_ids:
        for approval in db.scalars(select(Approval).where(Approval.step_id.in_(old_ids))):
            db.delete(approval)
        for step in task.steps:
            db.delete(step)
        db.flush()
    task.steps = [PlanStep(
        task_id=task.id, ordinal=index, description=step.description,
        tool_name=step.tool_name, args_json=json.dumps(step.args, sort_keys=True),
        args_hash=args_hash(step.args), risk_level=REGISTRY[step.tool_name].risk,
        state="pending", dependencies_json=json.dumps(step.dependencies),
    ) for index, step in enumerate(steps, start=1)]
    task.plan_version += 1
    task.updated_at = utc_now()
    record_event(db, task.id, "plan_updated", {"plan_version": task.plan_version, "step_count": len(steps)})


@router.post("", response_model=TaskView, status_code=201)
def create_task(body: TaskCreate, db: DbSession) -> TaskView:
    if body.workspace_path and body.input_files:
        raise HTTPException(status_code=422, detail="Choose an approved folder or attach files, not both")
    task_id = new_id()
    if body.workspace_path:
        allowed = {os.path.normcase(str(Path(item).resolve())) for item in get_settings().approved_workspaces.split(";") if item.strip()}
        selected = Path(body.workspace_path).resolve()
        if os.path.normcase(str(selected)) not in allowed or not selected.is_dir():
            raise HTTPException(status_code=403, detail="Folder is not in APPROVED_WORKSPACES")
        entries = list(islice(selected.iterdir(), 101))
        if len(entries) > 100:
            raise HTTPException(status_code=422, detail="Folder contains too many top-level entries")
        files = sorted(item.name for item in entries if item.is_file() and item.suffix.lower() in {".md", ".txt"})[:5]
        if not files:
            raise HTTPException(status_code=422, detail="Folder has no Markdown or text files")
        try:
            for name in files:
                workspace_file(str(selected), name)
        except (ToolDenied, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        workspace = selected
    elif body.input_files:
        files = [item.name for item in body.input_files]
        if len(set(files)) != len(files) or any(len(item.content.encode("utf-8")) > 65536 for item in body.input_files):
            raise HTTPException(status_code=422, detail="Input files must have unique names and be at most 64 KiB each")
        workspace = Path(get_settings().data_dir).resolve() / "workspaces" / task_id
        workspace.mkdir(parents=True, exist_ok=False)
        try:
            for item in body.input_files:
                (workspace / item.name).write_text(item.content, encoding="utf-8")
        except OSError as exc:
            raise HTTPException(status_code=500, detail="Could not store task inputs") from exc
    else:
        workspace = DEMO_WORKSPACE
        files = ["brief.md", "meeting.md"]
    task = Task(
        id=task_id,
        goal=body.goal, constraints_json=json.dumps(body.constraints),
        success_criteria=body.success_criteria, capabilities_json=json.dumps(body.capabilities),
        network_access=body.network_access, workspace_path=str(workspace), input_files_json=json.dumps(files), state="draft",
    )
    db.add(task)
    db.flush()
    record_event(db, task.id, "task_created", {"state": "draft"})
    db.commit()
    return task_view(task)


@router.get("", response_model=TaskList)
def list_tasks(db: DbSession, limit: int = 20, offset: int = 0, state: str | None = None, q: str | None = None) -> TaskList:
    if not 1 <= limit <= 100 or offset < 0 or (state is not None and state not in TRANSITIONS) or (q is not None and len(q) > 100):
        raise HTTPException(status_code=422, detail="Invalid pagination")
    criteria = []
    if state is not None:
        criteria.append(Task.state == state)
    if q:
        criteria.append(Task.goal.ilike(f"%{q}%"))
    rows = db.scalars(select(Task).options(selectinload(Task.steps)).where(*criteria).order_by(Task.created_at.desc(), Task.id.desc()).limit(limit).offset(offset)).all()
    total = db.scalar(select(func.count()).select_from(Task).where(*criteria)) or 0
    return TaskList(items=[task_view(task) for task in rows], total=total)


@router.get("/{task_id}", response_model=TaskView)
def read_task(task_id: str, db: DbSession) -> TaskView:
    return task_view(get_task(db, task_id))


@router.post("/{task_id}/plan", response_model=TaskView, status_code=202)
def plan_task(task_id: str, db: DbSession, body: PlanRequest | None = None) -> TaskView:
    task = get_task(db, task_id)
    if task.state not in {"draft", "review_required"}:
        raise HTTPException(status_code=409, detail="Task cannot be planned in its current state")
    capabilities = json.loads(task.capabilities_json)
    try:
        if body is not None and body.mode == "ollama":
            settings = get_settings()
            steps = generate_plan(task.goal, json.loads(task.constraints_json), capabilities, settings.ollama_endpoint, settings.ollama_model)
        else:
            steps = validate_steps(demo_plan(capabilities, json.loads(task.input_files_json)), capabilities)
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ModelPlanInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    transition(task, "planning")
    replace_steps(db, task, steps)
    transition(task, "review_required")
    record_event(db, task.id, "task_state", {"state": task.state})
    db.commit()
    return task_view(task)


@router.patch("/{task_id}/steps", response_model=TaskView)
def edit_plan(task_id: str, body: PlanEdit, db: DbSession) -> TaskView:
    task = get_task(db, task_id)
    if task.state != "review_required" or task.plan_version != body.plan_version:
        raise HTTPException(status_code=409, detail="Plan changed; reload before editing")
    try:
        steps = validate_steps(body.steps, json.loads(task.capabilities_json))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    replace_steps(db, task, steps)
    db.commit()
    return task_view(task)


@router.post("/{task_id}/start", response_model=TaskView, status_code=202)
def start_task(task_id: str, db: DbSession) -> TaskView:
    begin_write(db)
    task = get_task(db, task_id)
    if task.state != "review_required" or not task.steps:
        raise HTTPException(status_code=409, detail="A reviewed plan is required before starting")
    task.deadline_at = utc_now() + timedelta(seconds=get_settings().task_timeout_seconds)
    transition(task, "queued")
    record_event(db, task.id, "task_state", {"state": task.state})
    db.commit()
    return task_view(task)


@router.post("/{task_id}/cancel", response_model=TaskView, status_code=202)
def cancel_task(task_id: str, db: DbSession) -> TaskView:
    begin_write(db)
    task = get_task(db, task_id)
    try:
        transition(task, "cancelled")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record_event(db, task.id, "task_state", {"state": task.state})
    db.commit()
    return task_view(task)


@router.post("/{task_id}/pause", response_model=TaskView, status_code=202)
def pause_task(task_id: str, db: DbSession) -> TaskView:
    begin_write(db)
    task = get_task(db, task_id)
    try:
        transition(task, "pausing")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record_event(db, task.id, "task_state", {"state": task.state})
    db.commit()
    return task_view(task)


@router.post("/{task_id}/resume", response_model=TaskView, status_code=202)
def resume_task(task_id: str, db: DbSession) -> TaskView:
    begin_write(db)
    task = get_task(db, task_id)
    try:
        transition(task, "queued")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record_event(db, task.id, "task_state", {"state": task.state})
    db.commit()
    return task_view(task)
