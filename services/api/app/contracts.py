from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Capability = Literal["read_file", "search_local_docs", "write_report"]


class InputFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-zA-Z0-9_-]+\.(md|txt)$", max_length=100)
    content: str = Field(max_length=65536)


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: str = Field(min_length=8, max_length=4000)
    constraints: list[str] = Field(default_factory=list, max_length=12)
    success_criteria: str | None = Field(default=None, max_length=2000)
    capabilities: list[Capability] = Field(default_factory=lambda: ["read_file", "search_local_docs", "write_report"], max_length=3)
    network_access: bool = False
    workspace_path: str | None = Field(default=None, max_length=500)
    input_files: list[InputFile] = Field(default_factory=list, max_length=5)

    @field_validator("goal")
    @classmethod
    def nonblank_goal(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Goal must contain non-whitespace text")
        return value.strip()


class StepInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=3, max_length=500)
    tool_name: Capability
    args: dict[str, Any]
    dependencies: list[int] = Field(default_factory=list, max_length=12)


class PlanEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_version: int = Field(ge=1)
    steps: list[StepInput] = Field(min_length=1, max_length=12)


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["demo", "ollama"] = "demo"


class StepView(BaseModel):
    id: str
    ordinal: int
    description: str
    tool_name: str
    args: dict[str, Any]
    args_hash: str
    risk_level: str
    state: str
    dependencies: list[int]


class TaskView(BaseModel):
    id: str
    goal: str
    constraints: list[str]
    success_criteria: str | None
    capabilities: list[str]
    network_access: bool
    workspace_path: str | None
    input_files: list[str]
    state: str
    plan_version: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    deadline_at: datetime | None
    steps: list[StepView]


class TaskList(BaseModel):
    items: list[TaskView]
    total: int


class ErrorBody(BaseModel):
    code: str
    message: str
    correlation_id: str


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]
    scope_hash: str = Field(min_length=64, max_length=64)


class ApprovalView(BaseModel):
    id: str
    task_id: str
    step_id: str
    scope_hash: str
    requested_action: str
    decision: str
    expires_at: datetime | None
