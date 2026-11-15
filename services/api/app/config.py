from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_host: str = "127.0.0.1"
    app_port: int = 8765
    database_url: str = "sqlite:///./data/nexus.db"
    demo_mode: bool = True
    ollama_endpoint: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    data_dir: str = "./data"
    approved_workspaces: str = ""
    task_timeout_seconds: int = Field(default=3600, ge=60, le=86400)


@lru_cache
def get_settings() -> Settings:
    return Settings()
