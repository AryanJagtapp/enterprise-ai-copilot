"""
BM25 sparse retrieval (rank_bm25). Rebuilt in-memory from the
`document_chunks` table at process startup and after each ingestion —
cheap at this project's scale (thousands, not millions, of chunks) and
avoids a second persisted index to keep in sync with SQLite.
"""
import re
import threading
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.db import DocumentChunk

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass
class SparseHit:
    chunk_id: str
    score: float


class SparseIndex:
    _lock = threading.Lock()

    def __init__(self):
        self._bm25 = None
        self._chunk_ids: List[str] = []

    def build(self, db: Session) -> None:
        from rank_bm25 import BM25Okapi

        with self._lock:
            rows = db.query(DocumentChunk).all()
            self._chunk_ids = [r.id for r in rows]
            tokenized = [_tokenize(r.text) for r in rows]
            self._bm25 = BM25Okapi(tokenized) if tokenized else None

    def is_built(self) -> bool:
        return self._bm25 is not None

    def search(self, query: str, top_k: int = 10, allowed_chunk_ids: Optional[set] = None) -> List[SparseHit]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self._chunk_ids, scores), key=lambda x: -x[1])
        hits: List[SparseHit] = []
        for chunk_id, score in ranked:
            if allowed_chunk_ids is not None and chunk_id not in allowed_chunk_ids:
                continue
            if score <= 0:
                continue
            hits.append(SparseHit(chunk_id=chunk_id, score=float(score)))
            if len(hits) >= top_k:
                break
        return hits


_default_index: Optional[SparseIndex] = None


def get_sparse_index() -> SparseIndex:
    global _default_index
    if _default_index is None:
        _default_index = SparseIndex()
    return _default_index


def reset_sparse_index_singleton() -> None:
    global _default_index
    _default_index = None
