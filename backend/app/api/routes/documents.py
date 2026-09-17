import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.db import Document, DocumentChunk, get_db
from app.rag.sparse_index import get_sparse_index
from app.rag.vector_store import get_vector_store
from app.services.ingestion import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str | None = Form(default=None),
    client_name: str | None = Form(default=None),
    business_unit: str | None = Form(default=None),
    department: str | None = Form(default=None),
    confidentiality_level: str = Form(default="Internal"),
    uploaded_by: str | None = Form(default=None),
    source: str = Form(default="manual_upload"),
    version: str = Form(default="1"),
    tags: str | None = Form(default=None),  # JSON-encoded list[str] or comma-separated
    db: Session = Depends(get_db),
):
    raw_bytes = await file.read()
    parsed_tags = []
    if tags:
        try:
            parsed_tags = json.loads(tags)
        except json.JSONDecodeError:
            parsed_tags = [t.strip() for t in tags.split(",") if t.strip()]

    try:
        document = ingest_document(
            db,
            filename=file.filename,
            raw_bytes=raw_bytes,
            document_type=document_type,
            client_name=client_name,
            business_unit=business_unit,
            department=department,
            confidentiality_level=confidentiality_level,
            uploaded_by=uploaded_by,
            source=source,
            version=version,
            tags=parsed_tags,
        )
    except AppError as exc:
        status_code = 409 if "duplicate_of" in exc.context else 422
        raise HTTPException(status_code=status_code, detail=exc.to_response()) from exc

    return {"document": document.to_metadata_dict(), "status": document.status, "chunk_count": document.chunk_count}


@router.get("")
def list_documents(status: str | None = None, business_unit: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Document)
    if status:
        query = query.filter(Document.status == status)
    if business_unit:
        query = query.filter(Document.business_unit == business_unit)
    rows = query.order_by(Document.uploaded_at.desc()).all()
    return [
        {**r.to_metadata_dict(), "status": r.status, "chunk_count": r.chunk_count, "error_message": r.error_message}
        for r in rows
    ]


@router.delete("/{document_id}")
def delete_document(document_id: str, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Document not found."})

    chunk_rows = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).all()
    chunk_ids = [c.id for c in chunk_rows]

    get_vector_store().delete_by_ids(chunk_ids)
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
    db.delete(document)
    db.commit()

    get_sparse_index().build(db)  # rebuild so deleted chunks stop appearing in BM25 results

    return {"deleted": document_id, "chunks_removed": len(chunk_ids)}
