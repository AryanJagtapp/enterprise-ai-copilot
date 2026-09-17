import numpy as np

from app.rag.vector_store import VectorStore


def test_add_and_search_roundtrip(tmp_path):
    store = VectorStore(path=str(tmp_path / "vecstore"))
    vectors = np.array([[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]], dtype=np.float32)
    store.add(["a", "b", "c"], vectors)
    assert store.count() == 3

    hits = store.search(np.array([1.0, 0.0], dtype=np.float32), top_k=2)
    assert hits[0].chunk_id == "a"


def test_delete_by_ids(tmp_path):
    store = VectorStore(path=str(tmp_path / "vecstore2"))
    vectors = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    store.add(["x", "y"], vectors)
    store.delete_by_ids(["x"])
    assert store.count() == 1
    hits = store.search(np.array([1.0, 0.0], dtype=np.float32), top_k=5)
    assert all(h.chunk_id != "x" for h in hits)


def test_persistence_across_instances(tmp_path):
    path = str(tmp_path / "vecstore3")
    store1 = VectorStore(path=path)
    store1.add(["p"], np.array([[1.0, 1.0]], dtype=np.float32))

    store2 = VectorStore(path=path)
    assert store2.count() == 1
