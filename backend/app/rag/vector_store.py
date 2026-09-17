"""
Dense vector store.

Design choice: a small, dependency-light flat-file store (numpy array +
JSON id map) rather than pulling in a full vector database (Chroma etc).
At this project's scale (an internal knowledge base, not billions of
vectors) a brute-force cosine-similarity scan over a numpy matrix is
fast, has zero extra moving parts to deploy, and is trivially inspectable
for a manager review. The interface below (`add`, `search`, `delete_by_document`)
is the seam: swapping in Chroma/FAISS/pgvector later means reimplementing
this module only — nothing upstream changes.

Persistence: `<vector_store_path>/vectors.npy` + `<vector_store_path>/ids.json`.
"""
import json
import os
import threading
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from app.core.config import get_settings


@dataclass
class VectorHit:
    chunk_id: str
    score: float


class VectorStore:
    _lock = threading.Lock()

    def __init__(self, path: Optional[str] = None):
        settings = get_settings()
        self.path = path or settings.vector_store_path
        os.makedirs(self.path, exist_ok=True)
        self._vectors_path = os.path.join(self.path, "vectors.npy")
        self._ids_path = os.path.join(self.path, "ids.json")
        self._ids: List[str] = []
        self._matrix: Optional[np.ndarray] = None
        self._load()

    def _load(self) -> None:
        if os.path.exists(self._vectors_path) and os.path.exists(self._ids_path):
            self._matrix = np.load(self._vectors_path)
            with open(self._ids_path, "r", encoding="utf-8") as f:
                self._ids = json.load(f)
        else:
            self._matrix = np.zeros((0, 384), dtype=np.float32)
            self._ids = []

    def _save(self) -> None:
        np.save(self._vectors_path, self._matrix)
        with open(self._ids_path, "w", encoding="utf-8") as f:
            json.dump(self._ids, f)

    def add(self, chunk_ids: List[str], vectors: np.ndarray) -> None:
        if len(chunk_ids) == 0:
            return
        with self._lock:
            if self._matrix.shape[0] == 0:
                self._matrix = vectors.astype(np.float32)
            else:
                self._matrix = np.vstack([self._matrix, vectors.astype(np.float32)])
            self._ids.extend(chunk_ids)
            self._save()

    def delete_by_ids(self, chunk_ids_to_remove: List[str]) -> None:
        with self._lock:
            if not self._ids:
                return
            keep_mask = np.array([cid not in set(chunk_ids_to_remove) for cid in self._ids])
            self._ids = [cid for cid, keep in zip(self._ids, keep_mask) if keep]
            self._matrix = self._matrix[keep_mask] if self._matrix.shape[0] else self._matrix
            self._save()

    def search(self, query_vector: np.ndarray, top_k: int = 10, allowed_chunk_ids: Optional[set] = None) -> List[VectorHit]:
        if self._matrix.shape[0] == 0:
            return []
        scores = self._matrix @ query_vector  # both L2-normalized -> cosine similarity
        order = np.argsort(-scores)
        hits: List[VectorHit] = []
        for idx in order:
            chunk_id = self._ids[idx]
            if allowed_chunk_ids is not None and chunk_id not in allowed_chunk_ids:
                continue
            hits.append(VectorHit(chunk_id=chunk_id, score=float(scores[idx])))
            if len(hits) >= top_k:
                break
        return hits

    def count(self) -> int:
        return len(self._ids)


_default_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _default_store
    if _default_store is None:
        _default_store = VectorStore()
    return _default_store


def reset_vector_store_singleton() -> None:
    """Test helper — forces the next get_vector_store() call to re-read from disk/settings."""
    global _default_store
    _default_store = None
