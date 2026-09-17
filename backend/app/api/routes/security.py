from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models.db import SecurityEvent, get_db

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/events")
def list_security_events(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "event_type": r.event_type,
            "severity": r.severity,
            "request_id": r.request_id,
            "detail": r.detail,
            "blocked": r.blocked,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
