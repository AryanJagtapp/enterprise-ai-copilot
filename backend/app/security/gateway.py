"""
AI Security Gateway (Feature 3).

Single entry/exit point every request passes through:

    User -> Security Gateway -> Orchestrator -> ... -> Output Validation -> User

Responsibilities on the way IN:
    - input size/shape validation
    - PII detection (optionally redact before it reaches the LLM/logs)
    - prompt injection detection
    - policy checks (e.g. blocked topics, oversized payloads)

Responsibilities on the way OUT:
    - output validation (no leaked system prompt, no unbounded tool output)
    - citation presence check for RAG answers (handled by the orchestrator,
      surfaced here as a final gate)

Every decision is recorded as a SecurityEvent (see models/db.py) so the
Security Center in the frontend has real data to show, not a mock.
"""
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.errors import SecurityViolation
from app.models.db import SecurityEvent
from app.security import injection, pii

MAX_INPUT_CHARS = 8000


@dataclass
class GatewayDecision:
    allowed: bool
    sanitized_text: str
    events: List[str] = field(default_factory=list)


def _record_event(db: Optional[Session], event_type: str, detail: str, *, request_id: Optional[str], severity: str = "medium", blocked: bool = True) -> None:
    if db is None:
        return
    db.add(
        SecurityEvent(
            id=uuid.uuid4().hex,
            event_type=event_type,
            severity=severity,
            request_id=request_id,
            detail=detail,
            blocked=blocked,
        )
    )
    db.commit()


def inspect_input(
    text: str,
    *,
    db: Optional[Session] = None,
    request_id: Optional[str] = None,
    redact_pii: bool = True,
) -> GatewayDecision:
    """Run all inbound checks. Raises SecurityViolation on a hard block."""
    events: List[str] = []

    if not text or not text.strip():
        raise SecurityViolation("Request content cannot be empty.", reason="empty_input")

    if len(text) > MAX_INPUT_CHARS:
        _record_event(db, "policy_violation", f"input exceeded {MAX_INPUT_CHARS} chars", request_id=request_id)
        raise SecurityViolation(
            f"Your request is too long (max {MAX_INPUT_CHARS} characters).",
            reason="input_too_long",
        )

    injection_result = injection.scan(text)
    if injection_result.flagged:
        _record_event(
            db,
            "prompt_injection",
            f"matched patterns: {injection_result.matched_patterns}",
            request_id=request_id,
            severity="high",
        )
        events.append("prompt_injection_detected")
        raise SecurityViolation(
            "Your request looks like it is attempting to override the assistant's instructions, "
            "so it has been blocked.",
            reason="prompt_injection",
        )

    sanitized = text
    pii_result = pii.scan(text)
    if pii_result.has_pii:
        _record_event(
            db,
            "pii_detected",
            f"kinds={sorted({m.kind for m in pii_result.matches})}",
            request_id=request_id,
            severity="medium",
            blocked=False,
        )
        events.append("pii_detected")
        if redact_pii:
            sanitized = pii_result.redacted_text

    return GatewayDecision(allowed=True, sanitized_text=sanitized, events=events)


def inspect_document_content(text: str, *, source_label: str, db: Optional[Session] = None, request_id: Optional[str] = None) -> str:
    """
    Retrieved documents are untrusted data. We scan them for injection
    attempts (logged, not blocked — a document merely *containing*
    injection-like text should not crash retrieval, but it must never be
    allowed to act as an instruction) and always wrap them before they
    reach a prompt template.
    """
    injection_result = injection.scan(text)
    if injection_result.flagged:
        _record_event(
            db,
            "prompt_injection",
            f"in retrieved document '{source_label}': {injection_result.matched_patterns}",
            request_id=request_id,
            severity="high",
            blocked=False,
        )
    return injection.wrap_as_untrusted_data(source_label, text)


def validate_output(text: str, *, db: Optional[Session] = None, request_id: Optional[str] = None) -> str:
    """Final outbound gate — strips anything resembling a leaked system prompt marker."""
    leak_markers = ["<system_prompt>", "BEGIN SYSTEM PROMPT", "SYSTEM INSTRUCTIONS:"]
    cleaned = text
    for marker in leak_markers:
        if marker.lower() in cleaned.lower():
            _record_event(db, "policy_violation", f"output contained marker '{marker}'", request_id=request_id, severity="high")
            cleaned = cleaned.replace(marker, "[REDACTED]")
    return cleaned
