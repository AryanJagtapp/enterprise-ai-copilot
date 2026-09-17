"""
PII detection (Feature 3 — Security Gateway).

Regex/pattern-based detector for common PII shapes. This is intentionally
NOT a heavyweight NER model for Phase 1 — it is a fast, dependency-light
first line of defense. A Hugging Face NER-based detector can be added
later as an additional layer (documented as a future enhancement in
docs/model-dependency-strategy.md) without changing this module's
interface.
"""
import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class PiiMatch:
    kind: str
    start: int
    end: int


@dataclass
class PiiScanResult:
    matches: List[PiiMatch] = field(default_factory=list)
    redacted_text: str = ""

    @property
    def has_pii(self) -> bool:
        return len(self.matches) > 0


_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"(?<!\d)(\+?\d{1,3}[-.\s]?)?(\(?\d{3,4}\)?[-.\s]?){2,3}\d{3,4}(?!\d)"),
    "ssn_or_national_id": re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b[A-Z]{2}\d{6,10}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "aadhaar": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}


def scan(text: str) -> PiiScanResult:
    matches: List[PiiMatch] = []
    for kind, pattern in _PATTERNS.items():
        for m in pattern.finditer(text):
            matches.append(PiiMatch(kind=kind, start=m.start(), end=m.end()))

    redacted = text
    # Redact from rightmost match first so earlier offsets stay valid.
    for match in sorted(matches, key=lambda m: m.start, reverse=True):
        redacted = redacted[: match.start] + f"[REDACTED_{match.kind.upper()}]" + redacted[match.end :]

    return PiiScanResult(matches=matches, redacted_text=redacted)
