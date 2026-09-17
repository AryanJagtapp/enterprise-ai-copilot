from app.rag import reranker
from app.rag.hybrid_retrieval import RetrievedChunk


def _chunks():
    return [
        RetrievedChunk(chunk_id="1", document_id="d", text="The sky is blue and the weather is nice today.", filename="f.txt", metadata={}, fused_score=0.5),
        RetrievedChunk(chunk_id="2", document_id="d", text="Employees accrue 1.5 days of paid leave per month.", filename="f.txt", metadata={}, fused_score=0.4),
    ]


def test_rerank_orders_by_relevance():
    chunks = _chunks()
    reranked, used_fallback, reason = reranker.rerank("how much paid leave per month", chunks, top_k=2)
    assert used_fallback is False
    assert reranked[0].chunk_id == "2"  # the leave-related chunk should rank first


def test_rerank_falls_back_when_model_unavailable(monkeypatch):
    from app.core.errors import DependencyUnavailable

    def _broken_loader(*args, **kwargs):
        raise DependencyUnavailable("reranker model", detail="simulated failure")

    monkeypatch.setattr(reranker, "_load_model", _broken_loader)
    chunks = _chunks()
    reranked, used_fallback, reason = reranker.rerank("query", chunks, top_k=2)
    assert used_fallback is True
    assert "simulated failure" in reason
    assert reranked == chunks[:2]  # original order preserved, not silently dropped


def test_rerank_empty_input_returns_empty():
    reranked, used_fallback, reason = reranker.rerank("q", [])
    assert reranked == []
    assert used_fallback is False
