"""POST /search — raw retrieval endpoint (no LLM synthesis), useful for
debugging retrieval quality independently of answer generation, and used
by the evaluation suite."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.db import get_db
from app.rag.hybrid_retrieval import build_metadata_filter_set, retrieve
from app.rag.reranker import rerank
from app.security import authorization

router = APIRouter(tags=["search"])


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    business_unit: str | None = None
    document_type: str | None = None
    client_name: str | None = None
    rerank_results: bool = True


@router.post("/search")
def search(payload: SearchRequest, request: Request, db: Session = Depends(get_db)):
    clearance_header = request.headers.get("x-user-clearance", "Internal")
    allowed_ids = build_metadata_filter_set(
        db, business_unit=payload.business_unit, document_type=payload.document_type, client_name=payload.client_name
    )
    result = retrieve(db, payload.query, top_k=payload.top_k * 2, allowed_chunk_ids=allowed_ids)

    clearance = authorization.clearance_for_confidentiality(clearance_header)
    authorized = authorization.filter_authorized_chunks(result.chunks, requester_clearance=clearance, db=db)

    fallback_reasons = [result.fallback_reason] if result.fallback_triggered else []
    if payload.rerank_results:
        reranked, rerank_fallback, rerank_reason = rerank(payload.query, authorized, top_k=payload.top_k)
        if rerank_fallback:
            fallback_reasons.append(rerank_reason)
    else:
        reranked = authorized[: payload.top_k]

    return {
        "strategy": result.strategy,
        "fallback_triggered": bool(fallback_reasons),
        "fallback_reasons": [r for r in fallback_reasons if r],
        "results": [
            {
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "filename": c.filename,
                "text": c.text,
                "score": c.fused_score,
                "metadata": c.metadata,
            }
            for c in reranked
        ],
    }
