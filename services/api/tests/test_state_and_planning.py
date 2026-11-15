import pytest

from app.contracts import StepInput
from app.models import PlanStep, Task
from app.planning import demo_plan, safe_local_workspace_path, safe_relative_path, validate_steps
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


@pytest.mark.parametrize("value", [
    "C:/secret.txt", "C:\\secret.txt", "C:secret.txt", "\\\\server\\share\\secret.txt",
    "//server/share/secret.txt", "\\\\?\\C:\\secret.txt", "\\\\.\\NUL", "/etc/passwd",
    "../secret.md", "folder/../secret.md", "folder\\..\\secret.md",
    "brief.md:secret", "", "bad\x00name.md", "bad\nname.md", "bad\tname.md",
])
def test_read_paths_are_portably_restricted(value: str) -> None:
    assert not safe_relative_path(value)


def test_nested_relative_text_path_is_allowed() -> None:
    assert safe_relative_path("notes/brief.md")


@pytest.mark.parametrize("value", ["\\\\server\\share", "//server/share", "\\\\?\\C:\\data", "\\\\.\\NUL", "relative/folder", "bad\x00folder", "bad\nfolder", "/tmp/file:stream"])
def test_workspace_paths_reject_network_device_and_ambiguous_syntax(value: str) -> None:
    assert not safe_local_workspace_path(value)


def test_existing_local_absolute_workspace_path_is_eligible(tmp_path) -> None:
    assert safe_local_workspace_path(str(tmp_path))
