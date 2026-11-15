"""Small user-editable preference surface; filesystem scope stays operator-owned."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import begin_write, get_db
from app.models import AppSetting, utc_now

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])
DbSession = Annotated[Session, Depends(get_db)]


class SettingsView(BaseModel):
    ollama_model: str
    ollama_timeout_seconds: int
    task_timeout_seconds: int
    retention_days: int
    approved_workspace_count: int
    network_access_enabled: bool = False


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ollama_model: str | None = Field(default=None, max_length=100, pattern=r"^[a-zA-Z0-9_.:/-]*$")
    ollama_timeout_seconds: int | None = Field(default=None, ge=10, le=180)
    task_timeout_seconds: int | None = Field(default=None, ge=60, le=86400)
    retention_days: Literal[0, 30, 90, 365] | None = None


def effective_settings(db: Session) -> SettingsView:
    defaults = get_settings()
    values = {row.key: row.value for row in db.scalars(select(AppSetting).where(AppSetting.key.in_(["ollama_model", "ollama_timeout_seconds", "task_timeout_seconds", "retention_days"]))).all()}
    return SettingsView(
        ollama_model=values.get("ollama_model", defaults.ollama_model),
        ollama_timeout_seconds=int(values.get("ollama_timeout_seconds", defaults.ollama_timeout_seconds)),
        task_timeout_seconds=int(values.get("task_timeout_seconds", defaults.task_timeout_seconds)),
        retention_days=int(values.get("retention_days", 0)),
        approved_workspace_count=len([item for item in defaults.approved_workspaces.split(";") if item.strip()]),
    )


@router.get("", response_model=SettingsView)
def read_settings(db: DbSession) -> SettingsView:
    return effective_settings(db)


@router.patch("", response_model=SettingsView)
def update_settings(body: SettingsUpdate, db: DbSession) -> SettingsView:
    begin_write(db)
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            db.merge(AppSetting(key=key, value=str(value).strip(), updated_at=utc_now()))
    db.commit()
    return effective_settings(db)
