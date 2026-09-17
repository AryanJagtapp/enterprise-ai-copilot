"""
Tool Gateway (Feature 3 — "Tool Authorization" stage in the security
architecture, and part of Feature 1's controlled agent loop).

Every tool call from the orchestrator goes through here, never directly.
Enforces:
    - an explicit allowlist of callable tools (no dynamic/arbitrary code)
    - schema validation of arguments (Pydantic, see tools/schemas.py)
    - a timeout per call
    - a per-request maximum number of tool calls (max_agent_steps)

This is intentionally the ONLY place `calculate()` or a DB/KB search
function is invoked from agent logic, so a security review has one
choke point to audit rather than scattered call sites.
"""
import concurrent.futures
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, ValidationError

from app.core.errors import ToolFailure
from app.tools import schemas
from app.tools.calculator import calculate


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    output: Any
    latency_ms: float
    error: str | None = None


class ToolSpec:
    def __init__(self, name: str, schema: type[BaseModel], fn: Callable[..., Any], needs_context: bool = False):
        self.name = name
        self.schema = schema
        self.fn = fn
        # needs_context=True tools receive the request's DB session / request_id /
        # clearance as their first argument (a ToolContext) — these are per-request
        # values, so they can never live in the static TOOL_REGISTRY below.
        self.needs_context = needs_context


@dataclass
class ToolContext:
    db: Any
    request_id: Optional[str] = None
    clearance: Optional[str] = None


def _calculator_fn(expression: str) -> float:
    return calculate(expression)


def _knowledge_base_search_fn(ctx: ToolContext, query: str, top_k: int = 5, document_filter: str | None = None) -> list[dict]:
    from app.rag.hybrid_retrieval import retrieve
    from app.rag.reranker import rerank
    from app.security import authorization

    result = retrieve(ctx.db, query, top_k=top_k * 2)
    clearance = authorization.clearance_for_confidentiality(ctx.clearance or "Internal")
    authorized = authorization.filter_authorized_chunks(result.chunks, requester_clearance=clearance, db=ctx.db, request_id=ctx.request_id)
    reranked, _, _ = rerank(query, authorized, top_k=top_k)
    return [
        {"chunk_id": c.chunk_id, "document_id": c.document_id, "filename": c.filename, "text": c.text[:500]}
        for c in reranked
    ]


def _structured_db_search_fn(ctx: ToolContext, table: str, filters: dict, limit: int = 20) -> list[dict]:
    """
    Query APPROVED structured tables only — the allowlist below, never an
    arbitrary table name or raw SQL. This is the "Structured Database
    Search" tool from the spec; Phase 2 exposes the `documents` metadata
    table (safe, non-sensitive) as the first approved table.
    """
    from app.models.db import Document

    approved_tables = {"documents": Document}
    model = approved_tables.get(table)
    if model is None:
        raise ToolFailure("structured_db_search", detail=f"table '{table}' is not on the approved allowlist {sorted(approved_tables)}")

    query = ctx.db.query(model)
    for key, value in (filters or {}).items():
        column = getattr(model, key, None)
        if column is None:
            raise ToolFailure("structured_db_search", detail=f"unknown filter field '{key}'")
        query = query.filter(column == value)

    rows = query.limit(limit).all()
    return [row.to_metadata_dict() if hasattr(row, "to_metadata_dict") else {"id": row.id} for row in rows]


# Registry is explicit and finite — no dynamic dispatch by string outside this table.
TOOL_REGISTRY: Dict[str, ToolSpec] = {
    "calculator": ToolSpec("calculator", schemas.CalculatorArgs, _calculator_fn),
    "knowledge_base_search": ToolSpec("knowledge_base_search", schemas.KnowledgeBaseSearchArgs, _knowledge_base_search_fn, needs_context=True),
    "structured_db_search": ToolSpec("structured_db_search", schemas.StructuredDbSearchArgs, _structured_db_search_fn, needs_context=True),
}


class ToolGateway:
    def __init__(self, timeout_seconds: int = 15, max_calls_per_request: int = 6):
        self.timeout_seconds = timeout_seconds
        self.max_calls_per_request = max_calls_per_request
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    def call(self, tool_name: str, raw_args: Dict[str, Any], *, calls_so_far: int, context: Optional[ToolContext] = None) -> ToolResult:
        start = time.perf_counter()

        if calls_so_far >= self.max_calls_per_request:
            raise ToolFailure(tool_name, detail="maximum agent steps exceeded")

        spec = TOOL_REGISTRY.get(tool_name)
        if spec is None:
            raise ToolFailure(tool_name, detail="tool is not on the allowlist")

        try:
            validated = spec.schema(**raw_args)
        except ValidationError as exc:
            raise ToolFailure(tool_name, detail=f"invalid arguments: {exc}") from exc

        if spec.needs_context:
            if context is None:
                raise ToolFailure(tool_name, detail="tool requires request context but none was provided")
            future = self._executor.submit(spec.fn, context, **validated.model_dump())
        else:
            future = self._executor.submit(spec.fn, **validated.model_dump())

        try:
            output = future.result(timeout=self.timeout_seconds)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise ToolFailure(tool_name, detail="tool call timed out", retriable=True)

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return ToolResult(tool_name=tool_name, success=True, output=output, latency_ms=latency_ms)
