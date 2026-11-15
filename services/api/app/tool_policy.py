import hashlib
import json
import os
import stat
from pathlib import Path

from pydantic import ValidationError

from app.models import PlanStep, Task
from app.planning import args_hash, safe_local_workspace_path, safe_relative_path
from app.registry import ARG_SCHEMAS


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
    if step.tool_name == "read_file" and not safe_relative_path(args["path"]):
        raise ToolDenied("Read path is outside the task workspace")


def approval_scope(task: Task, step: PlanStep) -> str:
    value = f"{task.id}:{task.plan_version}:{step.id}:{step.args_hash}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def workspace_file(root: str, relative: str) -> Path:
    if not safe_local_workspace_path(root):
        raise ToolDenied("Workspace path is not a local absolute folder")
    base = Path(root).resolve(strict=True)
    if not safe_relative_path(relative):
        raise ToolDenied("Only files inside the selected workspace may be read")
    candidate = (base / relative).resolve(strict=True)
    if not candidate.is_relative_to(base) or not candidate.is_file():
        raise ToolDenied("File is outside the selected workspace")
    if candidate.suffix.lower() not in {".md", ".txt"}:
        raise ToolDenied("Only Markdown and plain text files are supported")
    if candidate.stat().st_size > 65536:
        raise ToolDenied("File exceeds the 64 KiB read limit")
    return candidate


def read_workspace_text(root: str, relative: str) -> tuple[str, str]:
    path = workspace_file(root, relative)
    expected = path.stat()
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        actual = os.fstat(stream.fileno())
        if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino) or not stat.S_ISREG(actual.st_mode) or actual.st_size > 65536:
            raise ToolDenied("Selected file changed before it could be read")
        data = stream.read(65537)
    if len(data) > 65536:
        raise ToolDenied("File exceeds the 64 KiB read limit")
    return path.name, data.decode("utf-8")
