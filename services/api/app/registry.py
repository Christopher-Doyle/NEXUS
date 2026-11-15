"""The complete set of tool capabilities available to a task plan."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReadFileArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=240)


class SearchLocalDocsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=120)


class WriteReportArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(pattern=r"^[a-zA-Z0-9_-]+\.md$", max_length=100)


class ReadFileResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    content: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SearchMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    line: int = Field(ge=1)
    excerpt: str = Field(max_length=200)


class SearchLocalDocsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str
    matches: list[SearchMatch] = Field(max_length=20)
    truncated: bool


class WriteReportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_id: str
    filename: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    version: str
    description: str
    parameters: type[BaseModel]
    output: type[BaseModel]
    capability: str
    risk: Literal["low", "high"]
    timeout_seconds: int
    max_output_bytes: int
    resource_limits: dict[str, int]
    retry: Literal["safe_read", "manual_review"]
    idempotency: Literal["repeatable", "exclusive_create"]


REGISTRY = {
    "read_file": ToolSpec("read_file", "1", "Read one selected Markdown or text file", ReadFileArgs, ReadFileResult, "read_file", "low", 5, 400000, {"file_bytes": 65536}, "safe_read", "repeatable"),
    "search_local_docs": ToolSpec("search_local_docs", "1", "Search up to five selected local text files", SearchLocalDocsArgs, SearchLocalDocsResult, "search_local_docs", "low", 5, 32768, {"files": 5, "file_bytes": 65536, "matches": 20}, "safe_read", "repeatable"),
    "write_report": ToolSpec("write_report", "1", "Create one approved Markdown artifact", WriteReportArgs, WriteReportResult, "write_report", "high", 5, 1024, {"source_files": 5, "report_bytes": 400000}, "manual_review", "exclusive_create"),
}

ARG_SCHEMAS = {name: spec.parameters for name, spec in REGISTRY.items()}
