"""
Adaptive Agentic Orchestrator (Feature 1).

Phase 1 scope: the ROUTING POLICY itself, fully implemented and testable,
plus a working path for TOOL and CLARIFY/REFUSE. The RAG and MULTI_HOP
paths are wired to raise NotImplementedError with a clear message until
the retrieval layer (app/rag) lands in Phase 2 — the routing decision,
observability event, and security gate around them are real today.

Routing policy (deterministic heuristics for now; Phase 2 upgrades the
RAG/TOOL/MULTI_HOP split to use the Gemini-backed `orchestrator_router`
prompt for genuinely ambiguous queries):

    - Arithmetic-looking query                         -> TOOL (calculator)
    - Query needing 2+ comparative/causal hops          -> MULTI_HOP
    - Query too short/ambiguous to act on               -> CLARIFY
    - Query matching a disallowed pattern                -> REFUSE
    - Everything else                                    -> RAG

Explicit stopping criteria: at most `max_agent_steps` tool/retrieval
calls per request (enforced by ToolGateway, not by this class re-counting).
"""
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RoutePath(str, Enum):
    RAG = "RAG"
    TOOL = "TOOL"
    MULTI_HOP = "MULTI_HOP"
    CLARIFY = "CLARIFY"
    REFUSE = "REFUSE"


@dataclass
class RouteDecision:
    path: RoutePath
    reason: str
    tool_name: Optional[str] = None


_ARITHMETIC_RE = re.compile(r"^[\s\d()+\-*/.%^]+$")
_CALC_KEYWORDS_RE = re.compile(r"\b(calculate|compute|sum|total cost|what is \d)\b", re.I)
_MULTIHOP_KEYWORDS_RE = re.compile(
    r"\b(compare|difference between|changed (over|since)|versus|vs\.?|how (has|did) .* (change|evolve))\b", re.I
)
_DISALLOWED_RE = re.compile(r"\b(bypass|jailbreak|ignore your instructions)\b", re.I)


def decide_route(query: str) -> RouteDecision:
    stripped = query.strip()

    if not stripped or len(stripped) < 3:
        return RouteDecision(RoutePath.CLARIFY, "Query is too short to act on.")

    if _DISALLOWED_RE.search(stripped):
        return RouteDecision(RoutePath.REFUSE, "Query matches a disallowed instruction-override pattern.")

    if _ARITHMETIC_RE.match(stripped) or _CALC_KEYWORDS_RE.search(stripped):
        return RouteDecision(RoutePath.TOOL, "Query looks like an arithmetic/calculation request.", tool_name="calculator")

    if _MULTIHOP_KEYWORDS_RE.search(stripped):
        return RouteDecision(RoutePath.MULTI_HOP, "Query requires comparing/reasoning across multiple retrieval steps.")

    return RouteDecision(RoutePath.RAG, "Default path: single-shot grounded document retrieval.")
