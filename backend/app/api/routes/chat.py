"""
POST /chat — Phase 1 implementation.

Wires the full request path that is already real end-to-end:

    Security Gateway (input) -> Orchestrator (route decision) -> Tool
    Gateway (if TOOL path) -> Security Gateway (output) -> Observability
    event recorded -> response

The RAG and MULTI_HOP paths return a clear 501-style "not yet implemented"
payload rather than a fabricated answer — Phase 2 wires in app/rag once
document ingestion exists. This keeps the contract the frontend can build
against stable from day one.
"""
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.orchestrator import RoutePath, decide_route
from app.core.errors import AppError
from app.core.logging import get_request_id
from app.models.db import ObservabilityEvent, get_db
from app.security.gateway import inspect_input, validate_output
from app.tools.gateway import ToolGateway

router = APIRouter(tags=["chat"])
_tool_gateway = ToolGateway()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    request_id: str
    router_decision: str
    answer: str
    tools_used: list[str] = []
    citations: list[str] = []
    fallback_triggered: bool = False
    fallback_reason: str | None = None


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    start = time.perf_counter()
    request_id = get_request_id()

    try:
        gateway_decision = inspect_input(payload.message, db=db, request_id=request_id)
    except AppError as exc:
        raise HTTPException(status_code=400, detail=exc.to_response()) from exc

    route = decide_route(gateway_decision.sanitized_text)
    tools_used: list[str] = []
    answer: str

    if route.path == RoutePath.TOOL and route.tool_name == "calculator":
        try:
            result = _tool_gateway.call("calculator", {"expression": gateway_decision.sanitized_text}, calls_so_far=0)
            answer = f"{result.output}"
            tools_used.append("calculator")
        except AppError as exc:
            raise HTTPException(status_code=422, detail=exc.to_response()) from exc
    elif route.path == RoutePath.CLARIFY:
        answer = "Could you rephrase or add more detail to your question?"
    elif route.path == RoutePath.REFUSE:
        answer = "I can't help with that request."
    else:
        # RAG / MULTI_HOP — retrieval layer lands in Phase 2.
        answer = (
            f"Routing selected '{route.path.value}' ({route.reason}) but the retrieval pipeline "
            "is not implemented yet in this build (Phase 2). This response is a placeholder, "
            "not a fabricated answer."
        )

    answer = validate_output(answer, db=db, request_id=request_id)
    total_latency_ms = round((time.perf_counter() - start) * 1000, 2)

    db.add(
        ObservabilityEvent(
            id=uuid.uuid4().hex,
            request_id=request_id,
            endpoint="/chat",
            router_decision=route.path.value,
            tool_selected=route.tool_name,
            total_latency_ms=total_latency_ms,
        )
    )
    db.commit()

    return ChatResponse(
        request_id=request_id,
        router_decision=route.path.value,
        answer=answer,
        tools_used=tools_used,
    )
