"""
FastAPI application entrypoint.

Run locally with:  uvicorn app.main:app --reload --port 8000
"""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import chat, health, observability, prompts, security
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, get_request_id, log_event, set_request_id
from app.models.db import get_session_factory
from app.prompts.registry import seed_default_prompts

settings = get_settings()
configure_logging(level=settings.log_level, json_output=settings.log_json)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    session_factory = get_session_factory()
    db = session_factory()
    try:
        seed_default_prompts(db)
    finally:
        db.close()
    log_event(logger, "info", "application startup complete", environment=settings.environment)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:16])
    set_request_id(request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except AppError as exc:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        log_event(logger, "warning", "request failed", request_id=request_id, path=request.url.path, error_class=exc.error_class.value, latency_ms=latency_ms)
        return JSONResponse(status_code=400, content=exc.to_response())
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["x-request-id"] = request_id
    log_event(logger, "info", "request completed", request_id=request_id, path=request.url.path, status_code=response.status_code, latency_ms=latency_ms)
    return response


app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(chat.router, prefix=settings.api_prefix)
app.include_router(prompts.router, prefix=settings.api_prefix)
app.include_router(security.router, prefix=settings.api_prefix)
app.include_router(observability.router, prefix=settings.api_prefix)
