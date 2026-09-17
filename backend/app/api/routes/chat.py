"""
POST /chat — Phase 2: the full pipeline is now real end-to-end.

    Security Gateway (input) -> Orchestrator (route decision)
        -> TOOL: Tool Gateway (calculator | knowledge_base_search | structured_db_search)
        -> RAG: hybrid retrieval -> authorization filter -> rerank -> Gemini synthesis (or extractive fallback)
        -> MULTI_HOP: planner -> N retrievals -> merge -> authorization filter -> rerank -> synthesis
        -> CLARIFY / REFUSE: fixed safe responses
    -> Security Gateway (output) -> Observability event persisted (full latency
       breakdown + fallback flags + prompt_version) -> response

Requester clearance is read from the `X-User-Clearance` header (see
app/security/authorization.py for why this is a documented placeholder,
not real authentication) and defaults to "Internal".
"""
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.multi_hop import run_multi_hop
from app.agents.orchestrator import RoutePath, decide_route
from app.core.errors import AppError
from app.core.logging import get_request_id
from app.models.db import ObservabilityEvent, get_db
from app.rag.answer_synthesis import synthesize
from app.rag.hybrid_retrieval import build_metadata_filter_set, retrieve
from app.rag.reranker import rerank
from app.security import authorization
from app.security.gateway import inspect_input, validate_output
from app.tools.gateway import ToolContext, ToolGateway
from app.tools.query_parsing import parse_structured_db_query

router = APIRouter(tags=["chat"])
_tool_gateway = ToolGateway()


class ChatRequest(BaseModel):
    message: str
    business_unit: str | None = None
    document_type: str | None = None
    client_name: str | None = None


class ChatResponse(BaseModel):
    request_id: str
    router_decision: str
    answer: str
    tools_used: list[str] = []
    citations: list[str] = []
    sub_questions: list[str] = []
    retrieval_strategy: str | None = None
    fallback_triggered: bool = False
    fallback_reasons: list[str] = []
    prompt_version: str | None = None


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request, db: Session = Depends(get_db)):
    start = time.perf_counter()
    request_id = get_request_id()
    clearance_header = request.headers.get("x-user-clearance", "Internal")

    try:
        gateway_decision = inspect_input(payload.message, db=db, request_id=request_id)
    except AppError as exc:
        raise HTTPException(status_code=400, detail=exc.to_response()) from exc

    route = decide_route(gateway_decision.sanitized_text)
    tools_used: list[str] = []
    citations: list[str] = []
    sub_questions: list[str] = []
    retrieval_strategy: str | None = None
    fallback_reasons: list[str] = []
    prompt_version: str | None = None

    retrieval_latency_ms = rerank_latency_ms = llm_latency_ms = tool_latency_ms = None

    if route.path == RoutePath.TOOL and route.tool_name == "calculator":
        t0 = time.perf_counter()
        try:
            result = _tool_gateway.call("calculator", {"expression": gateway_decision.sanitized_text}, calls_so_far=0)
            answer = f"{result.output}"
            tools_used.append("calculator")
        except AppError as exc:
            raise HTTPException(status_code=422, detail=exc.to_response()) from exc
        tool_latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    elif route.path == RoutePath.TOOL and route.tool_name == "structured_db_search":
        t0 = time.perf_counter()
        parsed = parse_structured_db_query(gateway_decision.sanitized_text)
        context = ToolContext(db=db, request_id=request_id, clearance=clearance_header)
        try:
            result = _tool_gateway.call(
                "structured_db_search",
                {"table": parsed.table, "filters": parsed.filters, "limit": parsed.limit},
                calls_so_far=0,
                context=context,
            )
            rows = result.output
            tools_used.append("structured_db_search")
            if not rows:
                answer = "No documents matched that query."
            else:
                filter_desc = ", ".join(f"{k}={v}" for k, v in parsed.filters.items()) or "no filters"
                names = ", ".join(r["filename"] for r in rows[:10])
                answer = f"Found {len(rows)} document(s) ({filter_desc}): {names}"
                if len(rows) > 10:
                    answer += f", and {len(rows) - 10} more."
        except AppError as exc:
            raise HTTPException(status_code=422, detail=exc.to_response()) from exc
        tool_latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    elif route.path == RoutePath.CLARIFY:
        answer = "Could you rephrase or add more detail to your question?"

    elif route.path == RoutePath.REFUSE:
        answer = "I can't help with that request."

    elif route.path == RoutePath.RAG:
        allowed_ids = build_metadata_filter_set(
            db, business_unit=payload.business_unit, document_type=payload.document_type, client_name=payload.client_name
        )
        t0 = time.perf_counter()
        retrieval_result = retrieve(db, gateway_decision.sanitized_text, top_k=8, allowed_chunk_ids=allowed_ids)
        retrieval_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        retrieval_strategy = retrieval_result.strategy
        if retrieval_result.fallback_triggered:
            fallback_reasons.append(retrieval_result.fallback_reason)

        clearance = authorization.clearance_for_confidentiality(clearance_header)
        authorized_chunks = authorization.filter_authorized_chunks(
            retrieval_result.chunks, requester_clearance=clearance, db=db, request_id=request_id
        )

        t0 = time.perf_counter()
        reranked_chunks, rerank_fallback, rerank_reason = rerank(gateway_decision.sanitized_text, authorized_chunks, top_k=5)
        rerank_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        if rerank_fallback:
            fallback_reasons.append(rerank_reason)

        t0 = time.perf_counter()
        synthesis = synthesize(db, gateway_decision.sanitized_text, reranked_chunks, request_id=request_id)
        llm_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        answer = synthesis.answer
        citations = synthesis.citations
        prompt_version = synthesis.prompt_version
        if synthesis.used_fallback:
            fallback_reasons.append(synthesis.fallback_reason)

    elif route.path == RoutePath.MULTI_HOP:
        allowed_ids = build_metadata_filter_set(
            db, business_unit=payload.business_unit, document_type=payload.document_type, client_name=payload.client_name
        )
        t0 = time.perf_counter()
        multi_hop_result = run_multi_hop(db, gateway_decision.sanitized_text, allowed_chunk_ids=allowed_ids)
        retrieval_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        retrieval_strategy = "multi_hop"
        sub_questions = multi_hop_result.sub_questions
        if multi_hop_result.planning_fallback_used:
            fallback_reasons.append(multi_hop_result.planning_fallback_reason)
        if multi_hop_result.retrieval_fallback_triggered:
            fallback_reasons.append(multi_hop_result.retrieval_fallback_reason)

        clearance = authorization.clearance_for_confidentiality(clearance_header)
        authorized_chunks = authorization.filter_authorized_chunks(
            multi_hop_result.chunks, requester_clearance=clearance, db=db, request_id=request_id
        )

        t0 = time.perf_counter()
        reranked_chunks, rerank_fallback, rerank_reason = rerank(gateway_decision.sanitized_text, authorized_chunks, top_k=6)
        rerank_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        if rerank_fallback:
            fallback_reasons.append(rerank_reason)

        t0 = time.perf_counter()
        synthesis = synthesize(db, gateway_decision.sanitized_text, reranked_chunks, request_id=request_id)
        llm_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        answer = synthesis.answer
        citations = synthesis.citations
        prompt_version = synthesis.prompt_version
        if synthesis.used_fallback:
            fallback_reasons.append(synthesis.fallback_reason)
    else:
        answer = "Unrecognized routing decision."

    answer = validate_output(answer, db=db, request_id=request_id)
    fallback_reasons = [r for r in fallback_reasons if r]
    total_latency_ms = round((time.perf_counter() - start) * 1000, 2)

    db.add(
        ObservabilityEvent(
            id=uuid.uuid4().hex,
            request_id=request_id,
            endpoint="/chat",
            router_decision=route.path.value,
            retrieval_strategy=retrieval_strategy,
            tool_selected=route.tool_name,
            fallback_triggered=bool(fallback_reasons),
            fallback_reason="; ".join(fallback_reasons) if fallback_reasons else None,
            prompt_version=prompt_version,
            total_latency_ms=total_latency_ms,
            retrieval_latency_ms=retrieval_latency_ms,
            rerank_latency_ms=rerank_latency_ms,
            llm_latency_ms=llm_latency_ms,
            tool_latency_ms=tool_latency_ms,
        )
    )
    db.commit()

    return ChatResponse(
        request_id=request_id,
        router_decision=route.path.value,
        answer=answer,
        tools_used=tools_used,
        citations=citations,
        sub_questions=sub_questions,
        retrieval_strategy=retrieval_strategy,
        fallback_triggered=bool(fallback_reasons),
        fallback_reasons=fallback_reasons,
        prompt_version=prompt_version,
    )
