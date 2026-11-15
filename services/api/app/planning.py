import hashlib
import json
from pathlib import Path, PureWindowsPath

from pydantic import ValidationError

from app.contracts import StepInput
from app.registry import ARG_SCHEMAS

MAX_STEPS = 12


def safe_relative_path(value: str) -> bool:
    path = Path(value)
    windows = PureWindowsPath(value)
    return not (path.is_absolute() or value.startswith("/") or windows.drive or "\\" in value or ".." in path.parts)


def args_hash(args: dict) -> str:
    canonical = json.dumps(args, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_steps(steps: list[StepInput], capabilities: list[str]) -> list[StepInput]:
    if not 1 <= len(steps) <= MAX_STEPS:
        raise ValueError("A plan must contain between 1 and 12 steps")
    validated: list[StepInput] = []
    for ordinal, step in enumerate(steps, start=1):
        if step.tool_name not in capabilities:
            raise ValueError(f"Tool {step.tool_name} is not granted for this task")
        try:
            typed_args = ARG_SCHEMAS[step.tool_name].model_validate(step.args)
        except ValidationError as exc:
            raise ValueError(f"Invalid arguments for step {ordinal}: {exc.errors()}") from exc
        if len(set(step.dependencies)) != len(step.dependencies) or any(
            dependency < 1 or dependency >= ordinal for dependency in step.dependencies
        ):
            raise ValueError(f"Step {ordinal} has invalid dependencies")
        if step.tool_name == "read_file" and not safe_relative_path(typed_args.path):
            raise ValueError("Read paths must be relative to the task workspace")
        validated.append(step.model_copy(update={"args": typed_args.model_dump()}))
    return validated


def demo_plan(capabilities: list[str], files: list[str] | None = None) -> list[StepInput]:
    if "read_file" not in capabilities or "write_report" not in capabilities:
        raise ValueError("The demo plan requires read_file and write_report capabilities")
    sources = files if files is not None else ["brief.md", "meeting.md"]
    if not 1 <= len(sources) <= 5:
        raise ValueError("The demo plan requires 1 to 5 text files")
    steps = [StepInput(description=f"Read {name}", tool_name="read_file", args={"path": name}) for name in sources]
    steps.append(StepInput(description="Write a sourced Markdown report", tool_name="write_report", args={"filename": "project-report.md"}, dependencies=list(range(1, len(sources) + 1))))
    return steps
