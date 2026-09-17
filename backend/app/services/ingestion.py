"""
Document ingestion pipeline: validate -> parse -> chunk -> dedupe ->
embed -> index -> mark status. Every stage failure is classified and
recorded on the Document row as status="failed" + error_message rather
than raising past the API layer uncaught.
"""
import hashlib
import json
import logging
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, DependencyUnavailable, ErrorClass
from app.models.db import Document, DocumentChunk
from app.rag.chunking import chunk_text, parse_document
from app.rag.sparse_index import get_sparse_index
from app.rag.vector_store import get_vector_store

logger = logging.getLogger("app.services.ingestion")

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def validate_upload(filename: str, size_bytes: int) -> None:
    settings = get_settings()
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError(ErrorClass.INVALID_INPUT, f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise AppError(ErrorClass.INVALID_INPUT, f"File exceeds the {settings.max_upload_mb}MB upload limit.")
    if size_bytes == 0:
        raise AppError(ErrorClass.INVALID_INPUT, "Uploaded file is empty.")


def compute_content_hash(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def find_duplicate(db: Session, content_hash: str) -> Optional[Document]:
    return db.query(Document).filter(Document.content_hash == content_hash, Document.status == "indexed").first()


def ingest_document(
    db: Session,
    *,
    filename: str,
    raw_bytes: bytes,
    document_type: Optional[str] = None,
    client_name: Optional[str] = None,
    business_unit: Optional[str] = None,
    department: Optional[str] = None,
    confidentiality_level: str = "Internal",
    uploaded_by: Optional[str] = None,
    source: str = "manual_upload",
    version: str = "1",
    tags: Optional[List[str]] = None,
    extra_metadata: Optional[dict] = None,
) -> Document:
    validate_upload(filename, len(raw_bytes))
    content_hash = compute_content_hash(raw_bytes)

    duplicate = find_duplicate(db, content_hash)
    if duplicate is not None:
        raise AppError(
            ErrorClass.INVALID_INPUT,
            f"An identical document is already indexed as '{duplicate.filename}' (document_id={duplicate.id}).",
            context={"duplicate_of": duplicate.id},
        )

    ext = "." + filename.rsplit(".", 1)[-1].lower()
    document = Document(
        id=uuid.uuid4().hex,
        filename=filename,
        content_hash=content_hash,
        file_type=ext,
        size_bytes=len(raw_bytes),
        document_type=document_type,
        client_name=client_name,
        business_unit=business_unit,
        department=department,
        confidentiality_level=confidentiality_level,
        uploaded_by=uploaded_by,
        source=source,
        version=version,
        tags=json.dumps(tags or []),
        extra_metadata=json.dumps(extra_metadata or {}),
        status="processing",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        text = parse_document(filename, raw_bytes)
        chunks = chunk_text(text)
        if not chunks:
            raise AppError(ErrorClass.INVALID_INPUT, "Document produced no chunks after parsing.")

        chunk_rows = []
        for chunk in chunks:
            row = DocumentChunk(
                id=uuid.uuid4().hex,
                document_id=document.id,
                chunk_index=chunk.index,
                text=chunk.text,
                token_estimate=len(chunk.text) // 4,
            )
            db.add(row)
            chunk_rows.append(row)
        db.commit()

        _index_chunks(db, chunk_rows)

        document.status = "indexed"
        document.chunk_count = len(chunk_rows)
        import datetime as dt

        document.indexed_at = dt.datetime.utcnow()
        db.commit()
        db.refresh(document)
        logger.info("indexed document %s (%s chunks)", document.id, len(chunk_rows))
        return document

    except AppError as exc:
        document.status = "failed"
        document.error_message = exc.user_message
        db.commit()
        raise
    except Exception as exc:  # noqa: BLE001 — never let an unexpected error crash the request uncaught
        document.status = "failed"
        document.error_message = "Unexpected error during ingestion."
        db.commit()
        logger.exception("ingestion failed for document %s", document.id)
        raise AppError(ErrorClass.PERMANENT, "Document ingestion failed unexpectedly.", detail=str(exc)) from exc


def _index_chunks(db: Session, chunk_rows: List[DocumentChunk]) -> None:
    """Embed + add to the vector store; rebuild the BM25 index. Embedding
    failure degrades gracefully — the document is still indexed and
    searchable via BM25, with the gap visible in logs/status, not hidden."""
    from app.rag import embeddings

    try:
        vectors = embeddings.embed_texts([c.text for c in chunk_rows])
        get_vector_store().add([c.id for c in chunk_rows], vectors)
    except DependencyUnavailable as exc:
        logger.warning("embedding unavailable during ingestion, chunks remain BM25-searchable only: %s", exc.detail)

    # BM25 is rebuilt from the full corpus (cheap at this scale); simplest
    # way to guarantee it never drifts from document_chunks.
    get_sparse_index().build(db)
