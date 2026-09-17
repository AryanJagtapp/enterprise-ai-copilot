"""
Hybrid retrieval: fuses dense (embeddings + vector store) and sparse
(BM25) results via Reciprocal Rank Fusion (RRF) — chosen over a raw
weighted-score sum because dense cosine similarities and BM25 scores
live on different, incomparable scales; RRF only needs each list's rank
order, which makes the fusion robust without any tuning of a weight
hyperparameter.

Feature 4 contract: if the dense path is unavailable (embedding model
failed to load), retrieval falls back to BM25-only and the caller is
told a fallback was used — it does not silently drop dense retrieval
without saying so.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.core.errors import DependencyUnavailable
from app.models.db import Document, DocumentChunk
from app.rag import embeddings
from app.rag.sparse_index import get_sparse_index
from app.rag.vector_store import get_vector_store

RRF_K = 60  # standard RRF smoothing constant


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    text: str
    filename: str
    metadata: dict
    fused_score: float


@dataclass
class RetrievalResult:
    chunks: List[RetrievedChunk]
    strategy: str  # "hybrid" | "sparse_only" | "dense_only"
    fallback_triggered: bool
    fallback_reason: Optional[str]


def _rrf_fuse(*rank_lists: List[str]) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    for ranked_ids in rank_lists:
        for rank, chunk_id in enumerate(ranked_ids):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
    return scores


def build_metadata_filter_set(
    db: Session,
    *,
    business_unit: Optional[str] = None,
    document_type: Optional[str] = None,
    client_name: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Optional[Set[str]]:
    """
    Metadata filtering for RELEVANCE, not security — returns the set of
    chunk_ids belonging to documents that match the given business
    filters, or None if no filter was requested (meaning: don't restrict
    by metadata). Authorization is applied separately by the caller via
    app/security/authorization.py, on top of whatever this returns.
    """
    if not any([business_unit, document_type, client_name, tags]):
        return None

    query = db.query(Document).filter(Document.status == "indexed")
    if business_unit:
        query = query.filter(Document.business_unit == business_unit)
    if document_type:
        query = query.filter(Document.document_type == document_type)
    if client_name:
        query = query.filter(Document.client_name == client_name)
    matching_docs = query.all()

    if tags:
        matching_docs = [d for d in matching_docs if set(tags) & set(d.tags_list())]

    doc_ids = {d.id for d in matching_docs}
    chunk_rows = db.query(DocumentChunk.id).filter(DocumentChunk.document_id.in_(doc_ids)).all()
    return {r[0] for r in chunk_rows}


def retrieve(
    db: Session,
    query: str,
    *,
    top_k: int = 8,
    allowed_chunk_ids: Optional[Set[str]] = None,
) -> RetrievalResult:
    sparse_index = get_sparse_index()
    if not sparse_index.is_built():
        sparse_index.build(db)

    sparse_hits = sparse_index.search(query, top_k=top_k * 3, allowed_chunk_ids=allowed_chunk_ids)
    sparse_ranked_ids = [h.chunk_id for h in sparse_hits]

    dense_ranked_ids: List[str] = []
    fallback_triggered = False
    fallback_reason: Optional[str] = None
    strategy = "hybrid"

    try:
        query_vector = embeddings.embed_query(query)
        vector_store = get_vector_store()
        dense_hits = vector_store.search(query_vector, top_k=top_k * 3, allowed_chunk_ids=allowed_chunk_ids)
        dense_ranked_ids = [h.chunk_id for h in dense_hits]
    except DependencyUnavailable as exc:
        fallback_triggered = True
        fallback_reason = f"dense retrieval unavailable ({exc.detail}); used BM25-only fallback"
        strategy = "sparse_only"

    if not dense_ranked_ids and not fallback_triggered:
        strategy = "sparse_only"  # dense index simply has nothing yet (e.g. no docs ingested)

    fused_scores = _rrf_fuse(sparse_ranked_ids, dense_ranked_ids) if dense_ranked_ids else _rrf_fuse(sparse_ranked_ids)
    top_chunk_ids = sorted(fused_scores, key=lambda cid: -fused_scores[cid])[:top_k]

    if not top_chunk_ids:
        return RetrievalResult(chunks=[], strategy=strategy, fallback_triggered=fallback_triggered, fallback_reason=fallback_reason)

    chunk_rows = {r.id: r for r in db.query(DocumentChunk).filter(DocumentChunk.id.in_(top_chunk_ids)).all()}
    doc_ids = {c.document_id for c in chunk_rows.values()}
    doc_rows = {d.id: d for d in db.query(Document).filter(Document.id.in_(doc_ids)).all()}

    results: List[RetrievedChunk] = []
    for chunk_id in top_chunk_ids:
        chunk_row = chunk_rows.get(chunk_id)
        if chunk_row is None:
            continue
        doc_row = doc_rows.get(chunk_row.document_id)
        results.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                document_id=chunk_row.document_id,
                text=chunk_row.text,
                filename=doc_row.filename if doc_row else "unknown",
                metadata=doc_row.to_metadata_dict() if doc_row else {},
                fused_score=fused_scores[chunk_id],
            )
        )

    return RetrievalResult(chunks=results, strategy=strategy, fallback_triggered=fallback_triggered, fallback_reason=fallback_reason)
