import pytest

from app.contracts import StepInput
from app.models import PlanStep, Task
from app.planning import demo_plan, safe_relative_path, validate_steps
from app.state import transition
from app.tool_policy import ToolDenied, validate_invocation


def test_terminal_state_cannot_restart() -> None:
    task = Task(goal="Test", state="draft")
    transition(task, "cancelled")
    with pytest.raises(ValueError):
        transition(task, "queued")


def test_plan_rejects_ungranted_tool_and_future_dependency() -> None:
    with pytest.raises(ValueError, match="not granted"):
        validate_steps(demo_plan(["read_file", "write_report"]), ["read_file"])
    with pytest.raises(ValueError, match="invalid dependencies"):
        validate_steps([StepInput(description="Read sample", tool_name="read_file", args={"path": "brief.md"}, dependencies=[2])], ["read_file"])


def test_runtime_validation_rejects_changed_arguments() -> None:
    task = Task(goal="Read sample", capabilities_json='["read_file"]')
    step = PlanStep(tool_name="read_file", args_json='{"path":"meeting.md"}', args_hash="0" * 64)
    with pytest.raises(ToolDenied, match="changed"):
        validate_invocation(task, step)


@pytest.mark.parametrize("value", ["C:/secret.txt", "C:\\secret.txt", "\\\\server\\share\\secret.txt", "/etc/passwd", "../secret.md", "folder\\..\\secret.md"])
def test_read_paths_are_portably_restricted(value: str) -> None:
    assert not safe_relative_path(value)
