from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.ollama import model_status
from app.operations import router as operations_router
from app.tasks import router as tasks_router

app = FastAPI(title="NEXUS API", version="0.1.0")
app.include_router(tasks_router)
app.include_router(operations_router)

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
LOCAL_ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8765", "http://localhost:8765"}


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"code": f"http_{exc.status_code}", "message": str(exc.detail), "correlation_id": request.state.correlation_id})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"code": "validation_error", "message": "; ".join(str(item["msg"]) for item in exc.errors())[:500], "correlation_id": request.state.correlation_id})


@app.middleware("http")
async def local_intent(request: Request, call_next):
    request.state.correlation_id = str(uuid4())
    host = (request.url.hostname or "").lower()
    if host not in LOCAL_HOSTS:
        return JSONResponse(status_code=403, content={"code": "invalid_host", "message": "Use a local address", "correlation_id": request.state.correlation_id})
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in LOCAL_ORIGINS:
            return JSONResponse(status_code=403, content={"code": "invalid_origin", "message": "Origin is not allowed", "correlation_id": request.state.correlation_id})
        if request.headers.get("x-nexus-intent") != "local":
            return JSONResponse(status_code=403, content={"code": "missing_intent", "message": "Local intent header required", "correlation_id": request.state.correlation_id})
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = request.state.correlation_id
    return response


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


@app.get("/api/v1/model/status")
def local_model_status() -> dict:
    settings = get_settings()
    return model_status(settings.ollama_endpoint, settings.ollama_model)
