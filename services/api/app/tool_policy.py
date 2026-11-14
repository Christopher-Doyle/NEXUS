import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from app.models import PlanStep, Task
from app.planning import ARG_SCHEMAS, args_hash


class ToolDenied(Exception):
    pass


def validate_invocation(task: Task, step: PlanStep) -> None:
    if step.tool_name not in ARG_SCHEMAS or step.tool_name not in json.loads(task.capabilities_json):
        raise ToolDenied("Tool is not granted for this task")
    try:
        args = ARG_SCHEMAS[step.tool_name].model_validate_json(step.args_json).model_dump()
    except (ValidationError, ValueError) as exc:
        raise ToolDenied("Tool arguments are invalid") from exc
    if args_hash(args) != step.args_hash:
        raise ToolDenied("Tool arguments changed after plan validation")
    if step.tool_name == "read_file" and (Path(args["path"]).is_absolute() or ".." in Path(args["path"]).parts):
        raise ToolDenied("Read path is outside the task workspace")


def approval_scope(task: Task, step: PlanStep) -> str:
    value = f"{task.id}:{task.plan_version}:{step.id}:{step.args_hash}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def workspace_file(root: str, relative: str) -> Path:
    base = Path(root).resolve(strict=True)
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ToolDenied("Only files inside the selected workspace may be read")
    candidate = (base / path).resolve(strict=True)
    if not candidate.is_relative_to(base) or not candidate.is_file():
        raise ToolDenied("File is outside the selected workspace")
    if candidate.suffix.lower() not in {".md", ".txt"}:
        raise ToolDenied("Only Markdown and plain text files are supported")
    if candidate.stat().st_size > 65536:
        raise ToolDenied("File exceeds the 64 KiB read limit")
    return candidate
