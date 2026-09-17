"""
Dense embedding model wrapper (Hugging Face, local — no external API call).

Lazy-loaded singleton: the sentence-transformers model is only loaded into
memory the first time an embedding is actually needed, so `import app.main`
and the test suite stay fast when no embedding call happens.

If the model cannot be loaded (no internet access to download weights on
first run, out of memory, etc.) this raises DependencyUnavailable so the
RAG pipeline can apply Feature 4's fallback (degrade to BM25-only
retrieval) instead of crashing the request.
"""
import logging
from typing import List, Optional

import numpy as np

from app.core.config import get_settings
from app.core.errors import DependencyUnavailable

logger = logging.getLogger("app.rag.embeddings")

_model = None
_model_name: Optional[str] = None


def _load_model():
    global _model, _model_name
    settings = get_settings()
    if _model is not None and _model_name == settings.embedding_model:
        return _model
    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embedding_model)
        _model_name = settings.embedding_model
        logger.info("loaded embedding model %s", settings.embedding_model)
        return _model
    except Exception as exc:  # noqa: BLE001 — any load failure degrades the same way
        raise DependencyUnavailable("embedding model", detail=str(exc)) from exc


def embed_texts(texts: List[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    model = _load_model()
    vectors = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
    return vectors.astype(np.float32)


def embed_query(query: str) -> np.ndarray:
    return embed_texts([query])[0]


def is_available() -> bool:
    try:
        _load_model()
        return True
    except DependencyUnavailable:
        return False
