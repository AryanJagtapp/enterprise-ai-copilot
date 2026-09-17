"""
Regression test for the Phase 3 crash-safety fix (Feature 4, Failure
Recovery): a malformed active prompt template must degrade to the
extractive/heuristic fallback path, never raise an uncaught
KeyError/IndexError that would 500 the request.

Before this fix, `active_prompt.template.format(...)` was called
outside the try/except that catches DependencyUnavailable in both
answer_synthesis.synthesize() and multi_hop.plan_sub_questions().
"""
from app.agents.multi_hop import plan_sub_questions
from app.prompts.registry import PromptRegistry, seed_default_prompts
from app.rag.answer_synthesis import synthesize
from app.rag.hybrid_retrieval import RetrievedChunk


def test_synthesize_falls_back_gracefully_on_malformed_template(db_session):
    seed_default_prompts(db_session)
    registry = PromptRegistry(db_session)
    # Introduce an unmatched '{' — this used to raise an uncaught KeyError.
    registry.create_version(
        "rag_answer_synthesis",
        description="deliberately broken template for crash-fix regression test",
        template="Answer using {context_typo} for the question {query}",
        activate=True,
    )

    chunks = [
        RetrievedChunk(
            chunk_id="c1",
            document_id="d1",
            text="Our leave policy grants 20 days of annual leave.",
            filename="doc1.txt",
            metadata={},
            fused_score=0.9,
        )
    ]

    result = synthesize(db_session, "What is our leave policy?", chunks, request_id="test-req")
    assert result.used_fallback is True
    assert "malformed" in result.fallback_reason
    assert result.answer  # extractive fallback still produced *something*


def test_plan_sub_questions_falls_back_gracefully_on_malformed_template(db_session):
    seed_default_prompts(db_session)
    registry = PromptRegistry(db_session)
    registry.create_version(
        "multi_hop_planner",
        description="deliberately broken template for crash-fix regression test",
        template="Break down {query_typo} into sub-questions.",
        activate=True,
    )

    sub_questions, used_fallback, reason = plan_sub_questions(db_session, "Compare our 2023 and 2024 leave policy")
    assert used_fallback is True
    assert "malformed" in reason
    assert sub_questions  # heuristic split still produced at least one sub-question
