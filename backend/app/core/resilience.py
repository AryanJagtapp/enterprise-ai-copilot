"""
Failure Recovery & Fallback helpers (Feature 4).

`with_retry` wraps a call with bounded retries + exponential backoff, but
only for errors explicitly marked retriable (ErrorClass.TRANSIENT or
AppError.retriable=True) — we deliberately do not blindly retry
everything, per the project spec.

`with_fallback` runs a primary function and, on any DependencyUnavailable
or explicitly retriable failure, runs a fallback function instead and
returns a FallbackResult so callers (and observability) know a fallback
was used and why. Nothing is silently degraded.
"""
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

from app.core.errors import AppError, DependencyUnavailable

T = TypeVar("T")


def with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int = 2,
    backoff_seconds: float = 1.5,
) -> T:
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except AppError as exc:
            last_exc = exc
            if not exc.retriable or attempt == max_retries:
                raise
            time.sleep(backoff_seconds * (2**attempt))
    raise last_exc  # pragma: no cover — unreachable, satisfies type checkers


@dataclass
class FallbackResult:
    value: Any
    used_fallback: bool
    fallback_reason: Optional[str] = None


def with_fallback(
    primary: Callable[[], T],
    fallback: Callable[[], T],
    *,
    dependency_name: str = "dependency",
) -> FallbackResult:
    try:
        return FallbackResult(value=primary(), used_fallback=False)
    except DependencyUnavailable as exc:
        return FallbackResult(value=fallback(), used_fallback=True, fallback_reason=f"{dependency_name} unavailable: {exc.detail}")
    except AppError as exc:
        if exc.retriable:
            return FallbackResult(value=fallback(), used_fallback=True, fallback_reason=f"{dependency_name} error: {exc.detail}")
        raise
