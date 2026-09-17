"""
Central error classification (Feature 4 — Failure Recovery).

Every failure in the system is mapped to one of these classes so the
API layer can decide: retry, fall back, or return a clean user-facing
error without leaking internals (stack traces, secrets, prompts).
"""
from enum import Enum
from typing import Any, Dict, Optional


class ErrorClass(str, Enum):
    TRANSIENT = "transient"                    # safe to retry (timeouts, 5xx, rate limit)
    PERMANENT = "permanent"                     # retrying will not help (bad request shape)
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"  # vector DB / reranker / Gemini down
    INVALID_INPUT = "invalid_input"             # user/client sent something malformed
    SECURITY_VIOLATION = "security_violation"   # blocked by the security gateway
    MODEL_FAILURE = "model_failure"             # LLM returned unusable/invalid output
    TOOL_FAILURE = "tool_failure"               # a tool call failed or was refused


class AppError(Exception):
    """Base application error. Carries a classification and a safe user message."""

    def __init__(
        self,
        error_class: ErrorClass,
        user_message: str,
        *,
        detail: Optional[str] = None,
        retriable: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(detail or user_message)
        self.error_class = error_class
        self.user_message = user_message
        self.detail = detail
        self.retriable = retriable
        self.context = context or {}

    def to_response(self) -> Dict[str, Any]:
        """Safe, user-facing shape — never includes stack traces or secrets."""
        return {
            "error": self.error_class.value,
            "message": self.user_message,
        }


class SecurityViolation(AppError):
    def __init__(self, user_message: str, *, reason: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorClass.SECURITY_VIOLATION, user_message, detail=reason, retriable=False, context=context)


class DependencyUnavailable(AppError):
    def __init__(self, dependency: str, *, detail: Optional[str] = None):
        super().__init__(
            ErrorClass.DEPENDENCY_UNAVAILABLE,
            f"The {dependency} service is temporarily unavailable. A fallback was attempted where possible.",
            detail=detail,
            retriable=True,
            context={"dependency": dependency},
        )


class ToolFailure(AppError):
    def __init__(self, tool_name: str, *, detail: Optional[str] = None, retriable: bool = False):
        super().__init__(
            ErrorClass.TOOL_FAILURE,
            f"The '{tool_name}' tool could not complete the request.",
            detail=detail,
            retriable=retriable,
            context={"tool": tool_name},
        )
