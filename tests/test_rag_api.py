"""Smoke tests for the RAG API service (unit-level, no Docker needed)."""

from unittest.mock import patch, MagicMock


def test_chunk_text():
    """_chunk_text splits long text into bounded chunks."""
    from services.rag_api.main import _chunk_text

    text = " ".join(f"word{i}" for i in range(600))
    chunks = _chunk_text(text, max_tokens=256)
    assert len(chunks) == 3
    assert all(len(c.split()) <= 256 for c in chunks)


def test_chunk_text_short():
    from services.rag_api.main import _chunk_text

    chunks = _chunk_text("hello world", max_tokens=256)
    assert len(chunks) == 1
    assert chunks[0] == "hello world"


def test_vectorstore_fallback_mode():
    """VectorStore in fallback mode (no qdrant, no sentence-transformers) returns empty."""
    from services.rag_api.vectorstore import VectorStore

    with (
        patch("services.rag_api.vectorstore._QDRANT_AVAILABLE", False),
        patch("services.rag_api.vectorstore._EMBEDDINGS_AVAILABLE", False),
    ):
        store = VectorStore.__new__(VectorStore)
        store.collection = "test"
        store.vector_size = 384
        store._client = None
        store._model = None
        results = store.search("test query", top_k=3)
        assert results == []


def test_ingest_endpoint_missing_dir():
    """POST /ingest with non-existent directory returns 400."""
    from fastapi.testclient import TestClient

    with patch("services.rag_api.main._store", MagicMock()):
        from services.rag_api.main import app

        client = TestClient(app)
        resp = client.post("/ingest", json={"directory": "/nonexistent/path"})
        assert resp.status_code == 400


def test_health_endpoint():
    """GET /health returns 200."""
    from fastapi.testclient import TestClient
    from services.rag_api.main import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
