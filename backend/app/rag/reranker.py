"""
Cross-encoder reranking (Hugging Face `cross-encoder/ms-marco-MiniLM-L-6-v2`).

Feature 4 contract: reranker failure -> fallback to the hybrid-retrieval
order unchanged -> continue, with the fact recorded, never hidden.
"""
import logging
from typing import List, Optional, Tuple

from app.core.config import get_settings
from app.core.errors import DependencyUnavailable
from app.rag.hybrid_retrieval import RetrievedChunk

logger = logging.getLogger("app.rag.reranker")

_model = None
_model_name: Optional[str] = None


def _load_model():
    global _model, _model_name
    settings = get_settings()
    if _model is not None and _model_name == settings.reranker_model:
        return _model
    try:
        from sentence_transformers import CrossEncoder

        _model = CrossEncoder(settings.reranker_model)
        _model_name = settings.reranker_model
        logger.info("loaded reranker model %s", settings.reranker_model)
        return _model
    except Exception as exc:  # noqa: BLE001
        raise DependencyUnavailable("reranker model", detail=str(exc)) from exc


def rerank(query: str, chunks: List[RetrievedChunk], *, top_k: int = 5) -> Tuple[List[RetrievedChunk], bool, Optional[str]]:
    """Returns (reranked_chunks, fallback_triggered, fallback_reason)."""
    if not chunks:
        return [], False, None
    try:
        model = _load_model()
        pairs = [(query, c.text) for c in chunks]
        scores = model.predict(pairs)
        order = sorted(range(len(chunks)), key=lambda i: -scores[i])
        reranked = [chunks[i] for i in order][:top_k]
        return reranked, False, None
    except DependencyUnavailable as exc:
        reason = f"reranker unavailable ({exc.detail}); used hybrid-retrieval order unchanged"
        logger.warning(reason)
        return chunks[:top_k], True, reason
