import json
import logging
from datetime import UTC, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import engine, get_db
from app.models import WorkerHeartbeat, utc_now
from app.ollama import model_status
from app.operations import router as operations_router
from app.preferences import effective_settings
from app.preferences import router as preferences_router
from app.rate_limit import RateLimiter
from app.recovery import router as recovery_router
from app.tasks import router as tasks_router

app = FastAPI(title="NEXUS API", version="0.1.0")
app.include_router(tasks_router)
app.include_router(operations_router)
app.include_router(preferences_router)
app.include_router(recovery_router)
rate_limiter = RateLimiter()
logger = logging.getLogger("nexus.api")

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
LOCAL_ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8765", "http://localhost:8765"}
MAX_REQUEST_BYTES = 512 * 1024


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"code": f"http_{exc.status_code}", "message": str(exc.detail), "correlation_id": request.state.correlation_id})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    errors = [
        {"field": ".".join(str(part) for part in item["loc"]), "message": str(item["msg"])[:200], "type": str(item["type"])}
        for item in exc.errors()[:20]
    ]
    return JSONResponse(status_code=422, content={"code": "validation_error", "message": "; ".join(item["message"] for item in errors)[:500], "fields": errors, "correlation_id": request.state.correlation_id})


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    logger.error(json.dumps({"event": "request_failed", "correlation_id": correlation_id, "exception_type": type(exc).__name__}))
    return JSONResponse(status_code=500, content={"code": "internal_error", "message": "Request failed; consult the local log using the correlation ID", "correlation_id": correlation_id}, headers={"X-Correlation-ID": correlation_id})


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
        bucket = "planning" if request.url.path.endswith("/plan") else "mutation"
        retry_after = rate_limiter.retry_after(request.client.host if request.client else "local", bucket)
        if retry_after is not None:
            return JSONResponse(status_code=429, content={"code": "rate_limited", "message": "Too many local requests; retry shortly", "correlation_id": request.state.correlation_id}, headers={"Retry-After": str(retry_after), "X-Correlation-ID": request.state.correlation_id})
        oversized = lambda: JSONResponse(status_code=413, content={"code": "request_too_large", "message": "Request body exceeds 512 KiB", "correlation_id": request.state.correlation_id}, headers={"X-Correlation-ID": request.state.correlation_id})
        declared_size = request.headers.get("content-length")
        if declared_size is not None:
            try:
                if int(declared_size) < 0:
                    raise ValueError("negative length")
                if int(declared_size) > MAX_REQUEST_BYTES:
                    return oversized()
            except ValueError:
                return JSONResponse(status_code=400, content={"code": "invalid_content_length", "message": "Invalid Content-Length", "correlation_id": request.state.correlation_id})
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_REQUEST_BYTES:
                return oversized()
            body.extend(chunk)
        request._body = bytes(body)
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
def local_model_status(db: Annotated[Session, Depends(get_db)]) -> dict:
    settings = get_settings()
    return model_status(settings.ollama_endpoint, effective_settings(db).ollama_model)


@app.get("/api/v1/worker/status")
def worker_status(db: Annotated[Session, Depends(get_db)]) -> dict:
    cutoff = utc_now() - timedelta(seconds=10)
    active = db.scalar(select(func.count()).select_from(WorkerHeartbeat).where(WorkerHeartbeat.last_seen_at >= cutoff)) or 0
    latest = db.scalar(select(WorkerHeartbeat.last_seen_at).order_by(WorkerHeartbeat.last_seen_at.desc()).limit(1))
    if latest is not None and latest.tzinfo is None:
        latest = latest.replace(tzinfo=UTC)
    return {"active": active > 0, "active_count": active, "last_seen_at": latest}
