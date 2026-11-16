import hashlib
import html
import json
import os
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Artifact, Execution, PlanStep, Task
from app.network_policy import FetchDenied, fetch_https_text, validated_https_url
from app.registry import REGISTRY
from app.search import SEARCH_PROVIDER
from app.tool_policy import ToolDenied, read_workspace_text


def artifact_dir(data_dir: str, task_id: str) -> Path:
    data_root = Path(data_dir).resolve()
    artifact_root = data_root / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    if artifact_root.resolve() != artifact_root:
        raise ToolDenied("Artifact directory is redirected")
    root = artifact_root / task_id
    root.mkdir(exist_ok=True)
    if root.resolve() != root:
        raise ToolDenied("Task artifact directory is redirected")
    return root


def create_report_file(root: Path, filename: str, data: bytes) -> None:
    """Create exclusively relative to a pinned directory where supported."""
    if os.open in os.supports_dir_fd and hasattr(os, "O_DIRECTORY") and hasattr(os, "O_NOFOLLOW"):
        try:
            directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                original = os.fstat(directory_fd)
                current = os.stat(root, follow_symlinks=False)
                if (current.st_dev, current.st_ino) != (original.st_dev, original.st_ino):
                    raise ToolDenied("Report directory changed before write")
                file_fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
                with os.fdopen(file_fd, "wb") as output:
                    output.write(data)
                current = os.stat(root, follow_symlinks=False)
                if (current.st_dev, current.st_ino) != (original.st_dev, original.st_ino):
                    raise ToolDenied("Report directory changed during write")
            finally:
                os.close(directory_fd)
        except FileExistsError as exc:
            raise ToolDenied("Report file already exists; manual review is required") from exc
        except OSError as exc:
            raise ToolDenied("Report directory or file is unavailable") from exc
        return
    target = root / filename
    try:
        with target.open("xb") as output:
            output.write(data)
    except FileExistsError as exc:
        raise ToolDenied("Report file already exists; manual review is required") from exc


def report_bytes(db: Session, task: Task) -> bytes:
    readings = []
    for source_step in db.scalars(select(PlanStep).where(PlanStep.task_id == task.id, PlanStep.tool_name.in_(["read_file", "fetch_url"])).order_by(PlanStep.ordinal)):
        execution = db.scalar(select(Execution).where(Execution.step_id == source_step.id, Execution.status == "completed"))
        if execution is None or execution.result_json is None:
            raise ToolDenied("Source readings are incomplete")
        try:
            reading = REGISTRY[source_step.tool_name].output.model_validate_json(execution.result_json).model_dump()
            arguments = REGISTRY[source_step.tool_name].parameters.model_validate_json(source_step.args_json)
        except ValidationError as exc:
            raise ToolDenied("Source reading receipt is invalid") from exc
        source_path = arguments.path if source_step.tool_name == "read_file" else arguments.url
        if source_step.tool_name == "read_file":
            valid_source = reading["source"] == Path(source_path).name
        else:
            try:
                validated_https_url(reading["source"])
                valid_source = reading["requested_url"] == source_path
            except FetchDenied:
                valid_source = False
        if not valid_source or hashlib.sha256(reading["content"].encode("utf-8")).hexdigest() != reading["sha256"]:
            raise ToolDenied("Source reading provenance is invalid")
        reading["path"] = source_path if source_step.tool_name == "read_file" else reading["source"]
        readings.append(reading)
    if not readings:
        raise ToolDenied("A report requires at least one source reading")
    if len(readings) > REGISTRY["write_report"].resource_limits["source_files"]:
        raise ToolDenied("Report has too many source readings")
    lines = [f"# Report: {html.escape(task.goal, quote=False)}", "", "Generated from selected local and approved HTTPS text sources. The text below is extracted evidence, not a model-verified conclusion.", ""]
    for number, reading in enumerate(readings, start=1):
        quoted_content = "\n".join(f"> {html.escape(line, quote=False)}" for line in reading["content"].splitlines())
        lines += [f"## Source [{number}]: {html.escape(json.dumps(reading['path']), quote=False)}", "", quoted_content, ""]
    lines += ["## Citations", "", "Each citation identifies the exact text snapshot used above. Verify the SHA-256 against the source content in the task journal.", ""]
    for number, reading in enumerate(readings, start=1):
        line_count = len(reading["content"].splitlines())
        location = f"lines 1–{line_count}" if line_count else "empty file"
        lines.append(f"[{number}] {html.escape(json.dumps(reading['path']), quote=False)}, {location}, SHA-256 `{reading['sha256']}`.")
    data = "\n".join(lines).encode("utf-8")
    if len(data) > REGISTRY["write_report"].resource_limits["report_bytes"]:
        raise ToolDenied("Report exceeds the registered size limit")
    return data


def run_tool(db: Session, task: Task, step: PlanStep) -> dict:
    args = json.loads(step.args_json)
    if step.tool_name == "read_file":
        if not task.workspace_path:
            raise ToolDenied("No workspace is configured for this task")
        name, content = read_workspace_text(task.workspace_path, args["path"])
        return {"source": name, "content": content, "sha256": hashlib.sha256(content.encode()).hexdigest()}
    if step.tool_name == "search_local_docs":
        if not task.workspace_path:
            raise ToolDenied("No workspace is configured for this task")
        query = args["query"].strip()
        if len(query) < 2:
            raise ToolDenied("Search query is too short")
        return SEARCH_PROVIDER.search(task.workspace_path, json.loads(task.input_files_json), query)
    if step.tool_name == "fetch_url":
        if not task.network_access:
            raise ToolDenied("Network access is not enabled for this task")
        try:
            source, content = fetch_https_text(args["url"])
        except FetchDenied as exc:
            raise ToolDenied(str(exc)) from exc
        return {"requested_url": args["url"], "source": source, "content": content, "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()}
    if step.tool_name == "write_report":
        data = report_bytes(db, task)
        root = artifact_dir(get_settings().data_dir, task.id)
        target = root / args["filename"]
        create_report_file(root, args["filename"], data)
        artifact = Artifact(task_id=task.id, safe_path=str(target), sha256=hashlib.sha256(data).hexdigest(), media_type="text/markdown", size_bytes=len(data))
        db.add(artifact)
        db.flush()
        return {"artifact_id": artifact.id, "filename": target.name, "sha256": artifact.sha256}
    raise ToolDenied("Tool is not registered")
