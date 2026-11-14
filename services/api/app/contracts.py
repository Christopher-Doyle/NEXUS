from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Capability = Literal["read_file", "write_report"]


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: str = Field(min_length=8, max_length=4000)
    constraints: list[str] = Field(default_factory=list, max_length=12)
    success_criteria: str | None = Field(default=None, max_length=2000)
    capabilities: list[Capability] = Field(default_factory=lambda: ["read_file", "write_report"], max_length=2)
    network_access: bool = False

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
    state: str
    plan_version: int
    created_at: datetime
    updated_at: datetime
    steps: list[StepView]


class TaskList(BaseModel):
    items: list[TaskView]
    total: int


class ErrorBody(BaseModel):
    code: str
    message: str
    correlation_id: str
