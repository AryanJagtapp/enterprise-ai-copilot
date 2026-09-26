"""
FastAPI application entrypoint.

Run locally with:  uvicorn app.main:app --reload --port 8000
"""
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import chat, documents, evaluation, health, observability, prompts, search, security
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, log_event, set_request_id
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
app.include_router(documents.router, prefix=settings.api_prefix)
app.include_router(search.router, prefix=settings.api_prefix)
app.include_router(prompts.router, prefix=settings.api_prefix)
app.include_router(security.router, prefix=settings.api_prefix)
app.include_router(observability.router, prefix=settings.api_prefix)
app.include_router(evaluation.router, prefix=settings.api_prefix)

# Add this block at the very end of the file, after the last app.include_router(...) line:

_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=_frontend_dist / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(_frontend_dist / "index.html")

# --- Serve the built frontend (staging deployment only) ---------------------
# Registered LAST, after every API router above, so an actual /api/v1/* path
# is always matched by its real route first — this catch-all only ever
# receives requests that didn't match an API route. In local dev this block
# is simply skipped (frontend/dist doesn't exist; the Vite dev server serves
# the UI on its own port instead), so nothing about the local workflow
# changes. In staging (Render), the CI build step builds the frontend into
# frontend/dist, and this lets one web service serve both the UI and the API
# from the same origin.
_here = Path(__file__).resolve()
_candidates = [
    _here.parents[2] / "frontend" / "dist",   # repo_root/frontend/dist (expected layout)
    Path.cwd() / "frontend" / "dist",         # in case the start command's cwd differs
    Path.cwd().parent / "frontend" / "dist",  # one level up from cwd, as a fallback
]
_frontend_dist = next((p for p in _candidates if p.is_dir()), None)

log_event(
    logger, "info", "frontend dist lookup",
    resolved_file=str(_here),
    cwd=str(Path.cwd()),
    candidates=[str(p) for p in _candidates],
    found=str(_frontend_dist) if _frontend_dist else None,
)

if _frontend_dist:
    app.mount("/assets", StaticFiles(directory=_frontend_dist / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(_frontend_dist / "index.html")