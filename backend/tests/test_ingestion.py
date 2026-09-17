import pytest

from app.core.errors import AppError
from app.models.db import Document, DocumentChunk
from app.services.ingestion import ingest_document, validate_upload


def test_validate_upload_rejects_bad_extension():
    with pytest.raises(AppError):
        validate_upload("archive.zip", 100)


def test_validate_upload_rejects_oversized_file():
    with pytest.raises(AppError):
        validate_upload("big.txt", 999_999_999)


def test_ingest_txt_document_end_to_end(rag_isolated):
    db = rag_isolated
    text = (
        b"Fulcrum Digital Leave Policy.\n\n"
        b"Employees accrue 1.5 days of paid leave per month, totaling 18 days annually. "
        b"Sick leave is capped at 10 days per year."
    )
    document = ingest_document(
        db,
        filename="leave_policy.txt",
        raw_bytes=text,
        document_type="policy",
        business_unit="shared",
        confidentiality_level="Internal",
        tags=["hr", "policy"],
    )
    assert document.status == "indexed"
    assert document.chunk_count >= 1

    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
    assert len(chunks) == document.chunk_count
    assert "leave" in chunks[0].text.lower()

    metadata = document.to_metadata_dict()
    assert metadata["business_unit"] == "shared"
    assert metadata["tags"] == ["hr", "policy"]


def test_duplicate_upload_is_rejected(rag_isolated):
    db = rag_isolated
    raw_bytes = b"Some unique document content for dedup testing."
    ingest_document(db, filename="a.txt", raw_bytes=raw_bytes, document_type="policy")
    with pytest.raises(AppError):
        ingest_document(db, filename="a_copy.txt", raw_bytes=raw_bytes, document_type="policy")


def test_failed_parse_marks_document_failed(rag_isolated):
    db = rag_isolated
    with pytest.raises(AppError):
        ingest_document(db, filename="broken.pdf", raw_bytes=b"not a real pdf", document_type="policy")
    failed_doc = db.query(Document).filter(Document.filename == "broken.pdf").first()
    assert failed_doc is not None
    assert failed_doc.status == "failed"
    assert failed_doc.error_message
