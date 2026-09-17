"""
Strict tool argument schemas. Every tool the orchestrator can call must
declare a Pydantic schema here — the tool gateway validates arguments
against it before the tool ever runs (see tools/gateway.py).
"""
from pydantic import BaseModel, Field


class CalculatorArgs(BaseModel):
    expression: str = Field(..., max_length=200, description="A plain arithmetic expression, e.g. '2 + 2 * 3'")


class KnowledgeBaseSearchArgs(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)
    document_filter: str | None = Field(default=None, max_length=200)


class StructuredDbSearchArgs(BaseModel):
    table: str = Field(..., pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$", max_length=64)
    filters: dict = Field(default_factory=dict)
    limit: int = Field(default=20, ge=1, le=100)
