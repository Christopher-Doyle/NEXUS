import pytest

from app.contracts import StepInput
from app.models import PlanStep, Task
from app.planning import args_hash, validate_steps
from app.tool_runner import run_tool


def test_search_reads_only_selected_files_and_limits_results(tmp_path) -> None:
    (tmp_path / "selected.md").write_text("\n".join(["Atlas evidence"] * 30), encoding="utf-8")
    (tmp_path / "unselected.md").write_text("Atlas private", encoding="utf-8")
    task = Task(goal="Find Atlas", workspace_path=str(tmp_path), input_files_json='["selected.md"]', capabilities_json='["search_local_docs"]')
    step = PlanStep(task_id="task", ordinal=1, description="Search Atlas", tool_name="search_local_docs", args_json='{"query":"Atlas"}', args_hash=args_hash({"query": "Atlas"}), risk_level="low")
    result = run_tool(None, task, step)
    assert len(result["matches"]) == 20
    assert result["truncated"] is True
    assert all(match["source"] == "selected.md" for match in result["matches"])
    assert result["matches"][0] == {"source": "selected.md", "line": 1, "excerpt": "Atlas evidence"}


def test_search_plan_requires_grant_and_typed_query() -> None:
    step = StepInput(description="Search local notes", tool_name="search_local_docs", args={"query": "Atlas"})
    assert validate_steps([step], ["search_local_docs"])[0].args == {"query": "Atlas"}
    with pytest.raises(ValueError, match="not granted"):
        validate_steps([step], ["read_file"])
    with pytest.raises(ValueError, match="Invalid arguments"):
        validate_steps([step.model_copy(update={"args": {"query": "A"}})], ["search_local_docs"])
