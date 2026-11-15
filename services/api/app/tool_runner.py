import hashlib
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Artifact, Execution, PlanStep, Task
from app.registry import REGISTRY
from app.tool_policy import ToolDenied, workspace_file


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


def run_tool(db: Session, task: Task, step: PlanStep) -> dict:
    args = json.loads(step.args_json)
    if step.tool_name == "read_file":
        if not task.workspace_path:
            raise ToolDenied("No workspace is configured for this task")
        path = workspace_file(task.workspace_path, args["path"])
        content = path.read_text(encoding="utf-8")
        return {"source": path.name, "content": content, "sha256": hashlib.sha256(content.encode()).hexdigest()}
    if step.tool_name == "search_local_docs":
        if not task.workspace_path:
            raise ToolDenied("No workspace is configured for this task")
        query = args["query"].strip()
        if len(query) < 2:
            raise ToolDenied("Search query is too short")
        matches = []
        for name in json.loads(task.input_files_json)[:5]:
            path = workspace_file(task.workspace_path, name)
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if query.casefold() in line.casefold():
                    matches.append({"source": name, "line": line_number, "excerpt": line[:200]})
                    if len(matches) == 20:
                        return {"query": query, "matches": matches, "truncated": True}
        return {"query": query, "matches": matches, "truncated": False}
    if step.tool_name == "write_report":
        if not task.workspace_path:
            raise ToolDenied("No workspace is configured for this task")
        readings = []
        for source_step in db.scalars(select(PlanStep).where(PlanStep.task_id == task.id, PlanStep.tool_name == "read_file").order_by(PlanStep.ordinal)):
            execution = db.scalar(select(Execution).where(Execution.step_id == source_step.id, Execution.status == "completed"))
            if execution is None or execution.result_json is None:
                raise ToolDenied("Source readings are incomplete")
            reading = json.loads(execution.result_json)
            source_path = json.loads(source_step.args_json)["path"]
            if reading["source"] != Path(source_path).name or hashlib.sha256(reading["content"].encode("utf-8")).hexdigest() != reading["sha256"]:
                raise ToolDenied("Source reading provenance is invalid")
            reading["path"] = source_path
            readings.append(reading)
        if not readings:
            raise ToolDenied("A report requires at least one source reading")
        lines = [f"# Report: {task.goal}", "", "Generated from local source files. The text below is extracted evidence, not a model-verified conclusion.", ""]
        for number, reading in enumerate(readings, start=1):
            quoted_content = "\n".join(f"> {line}" for line in reading["content"].splitlines())
            lines += [f"## Source [{number}]: {json.dumps(reading['path'])}", "", quoted_content, ""]
        lines += ["## Citations", "", "Each citation identifies the exact text snapshot used above. Verify the SHA-256 against the source content in the task journal.", ""]
        for number, reading in enumerate(readings, start=1):
            line_count = len(reading["content"].splitlines())
            location = f"lines 1–{line_count}" if line_count else "empty file"
            lines.append(f"[{number}] {json.dumps(reading['path'])}, {location}, SHA-256 `{reading['sha256']}`.")
        content = "\n".join(lines)
        data = content.encode("utf-8")
        if len(data) > REGISTRY["write_report"].resource_limits["report_bytes"]:
            raise ToolDenied("Report exceeds the registered size limit")
        root = artifact_dir(get_settings().data_dir, task.id)
        target = root / args["filename"]
        try:
            with target.open("xb") as output:
                output.write(data)
        except FileExistsError as exc:
            raise ToolDenied("Report file already exists; manual review is required") from exc
        artifact = Artifact(task_id=task.id, safe_path=str(target), sha256=hashlib.sha256(data).hexdigest(), media_type="text/markdown", size_bytes=len(data))
        db.add(artifact)
        db.flush()
        return {"artifact_id": artifact.id, "filename": target.name, "sha256": artifact.sha256}
    raise ToolDenied("Tool is not registered")
