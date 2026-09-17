"""
Database layer — SQLite for local/staging (per project spec), SQLAlchemy
ORM so swapping to Postgres later is a connection-string change only.

Tables: documents, prompt_versions, evaluations, security_events,
observability_events. No API keys or secrets are ever stored here.
"""
import datetime as dt
import os

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    content_hash = Column(String, nullable=False, index=True)  # for duplicate detection
    file_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="processing")  # processing|indexed|failed
    error_message = Column(Text, nullable=True)
    chunk_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=dt.datetime.utcnow)
    indexed_at = Column(DateTime, nullable=True)


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id = Column(String, primary_key=True)  # e.g. "orchestrator_router"
    version = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    template = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="draft")  # draft|active|retired
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    activated_at = Column(DateTime, nullable=True)


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(String, primary_key=True)
    run_label = Column(String, nullable=False)  # e.g. "prompt_v2_vs_v1"
    metric_name = Column(String, nullable=False)
    metric_value = Column(Float, nullable=False)
    baseline_value = Column(Float, nullable=True)
    regression_detected = Column(Boolean, default=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)  # pii_detected|prompt_injection|blocked_tool|policy_violation
    severity = Column(String, nullable=False, default="medium")
    request_id = Column(String, nullable=True)
    detail = Column(Text, nullable=True)  # never raw PII — a description only
    blocked = Column(Boolean, default=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class ObservabilityEvent(Base):
    __tablename__ = "observability_events"

    id = Column(String, primary_key=True)
    request_id = Column(String, nullable=False, index=True)
    endpoint = Column(String, nullable=False)
    router_decision = Column(String, nullable=True)
    retrieval_strategy = Column(String, nullable=True)
    tool_selected = Column(String, nullable=True)
    fallback_triggered = Column(Boolean, default=False)
    fallback_reason = Column(String, nullable=True)
    prompt_version = Column(String, nullable=True)
    total_latency_ms = Column(Float, nullable=True)
    retrieval_latency_ms = Column(Float, nullable=True)
    rerank_latency_ms = Column(Float, nullable=True)
    llm_latency_ms = Column(Float, nullable=True)
    tool_latency_ms = Column(Float, nullable=True)
    token_usage = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Float, nullable=True)
    error_class = Column(String, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        db_path = settings.database_url.replace("sqlite:///", "")
        engine_kwargs = {"connect_args": {"check_same_thread": False}}
        if db_path == ":memory:":
            # A plain in-memory SQLite DB is per-connection; without a
            # shared StaticPool, the table created at startup would live
            # in a different connection than the one each request uses.
            engine_kwargs["poolclass"] = StaticPool
        else:
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        _engine = create_engine(settings.database_url, **engine_kwargs)
        Base.metadata.create_all(_engine)
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def get_db() -> Session:
    """FastAPI dependency — yields a DB session and closes it after the request."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()
