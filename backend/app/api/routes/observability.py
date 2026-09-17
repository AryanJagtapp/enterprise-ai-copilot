from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models.db import ObservabilityEvent, get_db

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("")
def list_observability_events(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(ObservabilityEvent).order_by(ObservabilityEvent.created_at.desc()).limit(limit).all()
    return [
        {
            "request_id": r.request_id,
            "endpoint": r.endpoint,
            "router_decision": r.router_decision,
            "retrieval_strategy": r.retrieval_strategy,
            "tool_selected": r.tool_selected,
            "fallback_triggered": r.fallback_triggered,
            "fallback_reason": r.fallback_reason,
            "prompt_version": r.prompt_version,
            "total_latency_ms": r.total_latency_ms,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
