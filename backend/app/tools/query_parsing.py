"""
Heuristic argument extraction for the structured-DB-search tool.

Deliberately NOT LLM-based: the spec's `tool_argument_extraction` prompt
exists in the Prompt Registry for a future Gemini-backed extractor, but
adding an LLM round-trip just to pull "business_unit=CD" out of a short
query would be unnecessary complexity for what a few regex checks handle
reliably. If a real deployment needs to parse much richer natural-language
DB queries, swap this module's internals — `parse_structured_db_query`'s
signature is the seam or the function.
"""
import re
from dataclasses import dataclass, field
from typing import Dict

_BUSINESS_UNITS = {"cd", "fd", "shared"}
_DOCUMENT_TYPES = {"policy", "contract", "runbook", "proposal"}

_BUSINESS_UNIT_RE = re.compile(r"\b(cd|fd|shared)\b", re.IGNORECASE)
_DOCUMENT_TYPE_RE = re.compile(r"\b(policy|policies|contract|contracts|runbook|runbooks|proposal|proposals)\b", re.IGNORECASE)

_STRUCTURED_DB_TRIGGER_RE = re.compile(
    r"\b(how many|count of|number of|list|show( me)?)\b.*\b(documents?|policies|contracts?|runbooks?|proposals?)\b",
    re.IGNORECASE,
)

_SINGULARIZE = {"policies": "policy", "contracts": "contract", "runbooks": "runbook", "proposals": "proposal"}


@dataclass
class StructuredDbQuery:
    table: str = "documents"
    filters: Dict[str, str] = field(default_factory=dict)
    limit: int = 20


def looks_like_structured_db_query(query: str) -> bool:
    return bool(_STRUCTURED_DB_TRIGGER_RE.search(query))


def parse_structured_db_query(query: str) -> StructuredDbQuery:
    filters: Dict[str, str] = {}

    bu_match = _BUSINESS_UNIT_RE.search(query)
    if bu_match:
        raw = bu_match.group(1).lower()
        filters["business_unit"] = "shared" if raw == "shared" else raw.upper()

    dt_match = _DOCUMENT_TYPE_RE.search(query)
    if dt_match:
        raw = dt_match.group(1).lower()
        filters["document_type"] = _SINGULARIZE.get(raw, raw)

    return StructuredDbQuery(table="documents", filters=filters, limit=20)
