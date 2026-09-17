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
from typing import Any, Callable, Dict

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
    def __init__(self, name: str, schema: type[BaseModel], fn: Callable[..., Any]):
        self.name = name
        self.schema = schema
        self.fn = fn


def _calculator_fn(expression: str) -> float:
    return calculate(expression)


# Registry is explicit and finite — no dynamic dispatch by string outside this table.
TOOL_REGISTRY: Dict[str, ToolSpec] = {
    "calculator": ToolSpec("calculator", schemas.CalculatorArgs, _calculator_fn),
    # "knowledge_base_search" and "structured_db_search" are wired up in
    # app/rag and app/services once the retrieval layer lands (Phase 2).
}


class ToolGateway:
    def __init__(self, timeout_seconds: int = 15, max_calls_per_request: int = 6):
        self.timeout_seconds = timeout_seconds
        self.max_calls_per_request = max_calls_per_request
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    def call(self, tool_name: str, raw_args: Dict[str, Any], *, calls_so_far: int) -> ToolResult:
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

        future = self._executor.submit(spec.fn, **validated.model_dump())
        try:
            output = future.result(timeout=self.timeout_seconds)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise ToolFailure(tool_name, detail="tool call timed out", retriable=True)

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return ToolResult(tool_name=tool_name, success=True, output=output, latency_ms=latency_ms)
