from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import text

from app.db import engine

app = FastAPI(title="NEXUS API", version="0.1.0")


class Health(BaseModel):
    status: str
    version: str


@app.get("/health", response_model=Health)
def health() -> Health:
    return Health(status="ok", version="0.1.0")


@app.get("/ready", response_model=Health)
def ready() -> Health:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return Health(status="ready", version="0.1.0")
