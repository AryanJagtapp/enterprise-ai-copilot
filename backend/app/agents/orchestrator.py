"""
Adaptive Agentic Orchestrator (Feature 1).

The ROUTING POLICY: a bounded, deterministic router with six explicit
outcomes. Every one of RAG, TOOL (calculator and structured-DB-search),
MULTI_HOP, CLARIFY, and REFUSE is wired to a real handler in
api/routes/chat.py — nothing here returns a placeholder.

Routing policy (deterministic heuristics; genuinely ambiguous queries
that don't match any heuristic fall through to RAG as the safe default —
this keeps the router auditable and testable without an LLM round-trip
just to pick a path. The `orchestrator_router` prompt in the Prompt
Registry documents the routing policy this code implements and is the
seam for an LLM-backed router later, if the heuristics prove too coarse
for a query shape they don't yet cover):

    - Query matching a disallowed pattern                -> REFUSE
    - Query too short/ambiguous to act on                 -> CLARIFY
    - Arithmetic-looking query                            -> TOOL (calculator)
    - "how many/list/count ... documents/policies/..."    -> TOOL (structured_db_search)
    - Query needing 2+ comparative/causal hops            -> MULTI_HOP
    - Everything else                                     -> RAG

Explicit stopping criteria: at most `max_agent_steps` tool/retrieval
calls per request (enforced by ToolGateway, not by this class re-counting).
"""
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.tools.query_parsing import looks_like_structured_db_query


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

    if looks_like_structured_db_query(stripped):
        return RouteDecision(
            RoutePath.TOOL,
            "Query asks for a count/list over document metadata — routed to the structured DB search tool rather than free-text retrieval.",
            tool_name="structured_db_search",
        )

    if _MULTIHOP_KEYWORDS_RE.search(stripped):
        return RouteDecision(RoutePath.MULTI_HOP, "Query requires comparing/reasoning across multiple retrieval steps.")

    return RouteDecision(RoutePath.RAG, "Default path: single-shot grounded document retrieval.")
