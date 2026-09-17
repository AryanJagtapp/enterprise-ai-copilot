from app.agents.multi_hop import run_multi_hop
from app.services.ingestion import ingest_document


def test_multi_hop_uses_heuristic_planner_without_gemini(rag_isolated):
    db = rag_isolated
    from app.prompts.registry import seed_default_prompts

    seed_default_prompts(db)

    ingest_document(
        db,
        filename="policy_2023.txt",
        raw_bytes=b"In 2023 the security policy required incident reports within 48 hours.",
        document_type="policy",
        business_unit="shared",
    )
    ingest_document(
        db,
        filename="policy_2024.txt",
        raw_bytes=b"In 2024 the security policy was updated to require incident reports within 24 hours.",
        document_type="policy",
        business_unit="shared",
    )

    result = run_multi_hop(db, "Compare our 2023 and 2024 security policies versus each other")
    assert result.planning_fallback_used is True  # no real Gemini key -> heuristic split
    assert len(result.sub_questions) >= 1
    assert result.chunks  # merged pool found something from the seeded docs


def test_multi_hop_caps_at_four_hops(rag_isolated):
    db = rag_isolated
    from app.agents.multi_hop import MAX_HOPS
    from app.prompts.registry import seed_default_prompts

    seed_default_prompts(db)
    result = run_multi_hop(db, "a versus b and how c and what d and how e versus f")
    assert len(result.sub_questions) <= MAX_HOPS
