import os

import pytest

from app.tool_policy import ToolDenied
from app.tool_runner import create_report_file


def test_report_file_is_exclusive(tmp_path) -> None:
    create_report_file(tmp_path, "report.md", b"first")
    with pytest.raises(ToolDenied, match="already exists"):
        create_report_file(tmp_path, "report.md", b"second")
    assert (tmp_path / "report.md").read_bytes() == b"first"


@pytest.mark.skipif(os.open not in os.supports_dir_fd or not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"), reason="directory handles unavailable")
def test_report_file_rejects_redirected_parent(tmp_path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    redirected = tmp_path / "redirected"
    redirected.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ToolDenied, match="directory"):
        create_report_file(redirected, "report.md", b"private")
    assert not (outside / "report.md").exists()
