from app.rag.hybrid_retrieval import build_metadata_filter_set, retrieve
from app.services.ingestion import ingest_document


def _seed(db):
    ingest_document(
        db,
        filename="leave_policy.txt",
        raw_bytes=b"Employees accrue 1.5 days of paid leave per month, totaling 18 days annually.",
        document_type="policy",
        business_unit="shared",
        confidentiality_level="Internal",
    )
    ingest_document(
        db,
        filename="incident_runbook.txt",
        raw_bytes=b"P1 security incidents must trigger a bridge call within 30 minutes of detection.",
        document_type="runbook",
        business_unit="CD",
        confidentiality_level="Confidential",
    )


def test_retrieve_finds_relevant_chunk(rag_isolated):
    db = rag_isolated
    _seed(db)
    result = retrieve(db, "how many days of paid leave per month", top_k=3)
    assert result.chunks
    assert any("1.5" in c.text for c in result.chunks)
    assert result.strategy in ("hybrid", "sparse_only", "dense_only")


def test_metadata_filter_restricts_to_business_unit(rag_isolated):
    db = rag_isolated
    _seed(db)
    allowed = build_metadata_filter_set(db, business_unit="CD")
    assert allowed is not None
    result = retrieve(db, "leave policy days", top_k=5, allowed_chunk_ids=allowed)
    # the leave policy doc is business_unit=shared, not CD, so it must not appear
    assert all("1.5" not in c.text for c in result.chunks)


def test_no_filter_returns_none(rag_isolated):
    db = rag_isolated
    assert build_metadata_filter_set(db) is None
