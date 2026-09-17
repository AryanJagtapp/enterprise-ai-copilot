"""
No real GEMINI_API_KEY is configured in tests (or in this sandbox), so
these tests exercise the REAL failure/fallback path — not a mock of it.
"""
import pytest

from app.core.errors import DependencyUnavailable
from app.rag.answer_synthesis import synthesize
from app.rag.hybrid_retrieval import RetrievedChunk
from app.services.gemini_client import generate
from tests.conftest import fresh_session


def test_generate_raises_dependency_unavailable_without_real_key():
    with pytest.raises(DependencyUnavailable):
        generate("hello")


def test_synthesize_falls_back_to_extractive_answer():
    db = fresh_session()
    from app.prompts.registry import seed_default_prompts

    seed_default_prompts(db)

    chunks = [
        RetrievedChunk(
            chunk_id="c1",
            document_id="d1",
            text="Employees accrue 1.5 days of paid leave per month, totaling 18 days annually.",
            filename="leave_policy.txt",
            metadata={},
            fused_score=1.0,
        )
    ]
    result = synthesize(db, "How many days of leave per month?", chunks)
    assert result.used_fallback is True
    assert "Gemini unavailable" in result.fallback_reason
    assert "1.5" in result.answer
    assert result.citations
    assert result.prompt_version is not None


def test_synthesize_with_no_chunks_returns_no_answer_without_calling_llm():
    db = fresh_session()
    from app.prompts.registry import seed_default_prompts

    seed_default_prompts(db)
    result = synthesize(db, "anything", [])
    assert result.used_fallback is False
    assert "No relevant documents" in result.answer
