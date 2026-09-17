from app.rag.hybrid_retrieval import RetrievedChunk
from app.security.authorization import ClearanceLevel, clearance_for_confidentiality, filter_authorized_chunks


def test_clearance_parsing():
    assert clearance_for_confidentiality("Restricted") == ClearanceLevel.RESTRICTED
    assert clearance_for_confidentiality("public") == ClearanceLevel.PUBLIC
    assert clearance_for_confidentiality("unknown-garbage") == ClearanceLevel.INTERNAL  # safe default


def _chunk(confidentiality: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="c1",
        document_id="d1",
        text="secret stuff",
        filename="f.txt",
        metadata={"confidentiality_level": confidentiality, "filename": "f.txt"},
        fused_score=1.0,
    )


def test_internal_user_cannot_see_restricted_chunk():
    chunks = [_chunk("Restricted")]
    allowed = filter_authorized_chunks(chunks, requester_clearance=ClearanceLevel.INTERNAL)
    assert allowed == []


def test_confidential_user_can_see_internal_chunk():
    chunks = [_chunk("Internal")]
    allowed = filter_authorized_chunks(chunks, requester_clearance=ClearanceLevel.CONFIDENTIAL)
    assert len(allowed) == 1


def test_mixed_chunks_filtered_correctly():
    chunks = [_chunk("Public"), _chunk("Internal"), _chunk("Confidential"), _chunk("Restricted")]
    allowed = filter_authorized_chunks(chunks, requester_clearance=ClearanceLevel.CONFIDENTIAL)
    assert len(allowed) == 3  # Restricted is dropped, the other three pass
