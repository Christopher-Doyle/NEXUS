from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class Task(Base):
    __tablename__ = "task"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    goal: Mapped[str] = mapped_column(Text)
    constraints_json: Mapped[str] = mapped_column(Text, default="[]")
    capabilities_json: Mapped[str] = mapped_column(Text, default="[]")
    network_access: Mapped[bool] = mapped_column(default=False)
    success_criteria: Mapped[str | None] = mapped_column(Text)
    workspace_path: Mapped[str | None] = mapped_column(Text)
    input_files_json: Mapped[str] = mapped_column(Text, default="[]")
    state: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    plan_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    steps: Mapped[list["PlanStep"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class PlanStep(Base):
    __tablename__ = "plan_step"
    __table_args__ = (UniqueConstraint("task_id", "ordinal"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("task.id"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    tool_name: Mapped[str] = mapped_column(String(64))
    args_json: Mapped[str] = mapped_column(Text)
    args_hash: Mapped[str] = mapped_column(String(64))
    risk_level: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(32), default="pending")
    dependencies_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    task: Mapped[Task] = relationship(back_populates="steps")


class Execution(Base):
    __tablename__ = "execution"
    __table_args__ = (UniqueConstraint("idempotency_key"), UniqueConstraint("step_id", "attempt"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    step_id: Mapped[str] = mapped_column(ForeignKey("plan_step.id"), index=True)
    attempt: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(64))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32))
    result_json: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(64))


class Approval(Base):
    __tablename__ = "approval"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    step_id: Mapped[str] = mapped_column(ForeignKey("plan_step.id"), index=True)
    scope_hash: Mapped[str] = mapped_column(String(64))
    requested_action: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Event(Base):
    __tablename__ = "event"
    __table_args__ = (Index("ix_event_task_seq", "task_id", "seq"),)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("task.id"))
    kind: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    correlation_id: Mapped[str] = mapped_column(String(36))


class Artifact(Base):
    __tablename__ = "artifact"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("task.id"), index=True)
    safe_path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    media_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ToolGrant(Base):
    __tablename__ = "tool_grant"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tool_name: Mapped[str] = mapped_column(String(64))
    resource_scope: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeat"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AppSetting(Base):
    __tablename__ = "app_setting"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
