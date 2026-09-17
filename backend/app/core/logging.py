"""
Structured logging.

Every log line is a JSON object so it can be shipped to any log
aggregator. We deliberately never log secrets, API keys, or raw PII —
see security/pii.py for redaction used before anything user-supplied
is logged.
"""
import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

SENSITIVE_KEYS = {"api_key", "gemini_api_key", "authorization", "password", "secret", "token"}


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def set_request_id(request_id: str) -> None:
    _request_id_ctx.set(request_id)


def get_request_id() -> str:
    return _request_id_ctx.get()


def _scrub(data: Dict[str, Any]) -> Dict[str, Any]:
    scrubbed = {}
    for k, v in data.items():
        if k.lower() in SENSITIVE_KEYS:
            scrubbed[k] = "***REDACTED***"
        else:
            scrubbed[k] = v
    return scrubbed


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": round(time.time(), 3),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", get_request_id()),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(_scrub(extra))
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)


def log_event(logger: logging.Logger, level: str, message: str, **fields: Any) -> None:
    """Emit a structured log line with arbitrary extra fields (auto-scrubbed)."""
    getattr(logger, level.lower())(message, extra={"extra_fields": fields, "request_id": get_request_id()})


class Timer:
    """Small context manager for measuring stage latency in milliseconds."""

    def __init__(self) -> None:
        self.elapsed_ms: Optional[float] = None
        self._start = 0.0

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.elapsed_ms = round((time.perf_counter() - self._start) * 1000, 2)
