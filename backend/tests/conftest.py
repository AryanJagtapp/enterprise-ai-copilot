import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def fresh_session():
    """A standalone in-memory DB session, isolated from the app's own
    engine — used by RAG/ingestion/evaluation tests that don't need the
    full FastAPI request cycle."""
    from app.models.db import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


@pytest.fixture()
def db_session():
    return fresh_session()


@pytest.fixture()
def rag_isolated(tmp_path, db_session):
    """Points the vector store + BM25 index at a scratch location for
    this test only, so tests never see chunks left over from another
    test's documents."""
    from app.core.config import get_settings
    from app.rag.sparse_index import reset_sparse_index_singleton
    from app.rag.vector_store import reset_vector_store_singleton

    settings = get_settings()
    original_path = settings.vector_store_path
    settings.vector_store_path = str(tmp_path / "vector_store")
    reset_vector_store_singleton()
    reset_sparse_index_singleton()
    yield db_session
    settings.vector_store_path = original_path
    reset_vector_store_singleton()
    reset_sparse_index_singleton()
