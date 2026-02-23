"""Thin wrapper around Qdrant + sentence-transformers.

Provides a *no-embeddings* fallback when sentence-transformers is unavailable
(e.g. CI environment) – in that mode, /ingest and /query still respond but
return empty results with a clear warning.
"""

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger("rag-api.vectorstore")

# ── Lazy imports ─────────────────────────────────────────────────────
_EMBEDDINGS_AVAILABLE = True
try:
    from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
except ImportError:
    _EMBEDDINGS_AVAILABLE = False
    log.warning("sentence-transformers not installed – running in no-embeddings fallback mode")

try:
    from qdrant_client import QdrantClient  # type: ignore[import-untyped]
    from qdrant_client.models import (  # type: ignore[import-untyped]
        Distance,
        PointStruct,
        VectorParams,
    )
    _QDRANT_AVAILABLE = True
except ImportError:
    _QDRANT_AVAILABLE = False
    log.warning("qdrant-client not installed – running in no-embeddings fallback mode")


class VectorStore:
    """Abstraction over Qdrant for document ingestion and semantic search."""

    def __init__(
        self,
        qdrant_url: str = "http://qdrant:6333",
        collection: str = "tradeops_kb",
        embedding_model: str = "all-MiniLM-L6-v2",
        vector_size: int = 384,
    ):
        self.collection = collection
        self.vector_size = vector_size
        self._client: Optional[Any] = None
        self._model: Optional[Any] = None

        if _QDRANT_AVAILABLE:
            self._client = QdrantClient(url=qdrant_url, timeout=10)
        if _EMBEDDINGS_AVAILABLE:
            self._model = SentenceTransformer(embedding_model)
            self.vector_size = self._model.get_sentence_embedding_dimension()  # type: ignore[union-attr]

    # ── Collection management ────────────────────────────────────────

    def ensure_collection(self) -> None:
        if self._client is None:
            log.warning("Qdrant unavailable – skipping collection creation")
            return
        collections = [c.name for c in self._client.get_collections().collections]
        if self.collection not in collections:
            self._client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )
            log.info("Created Qdrant collection %s (dim=%d)", self.collection, self.vector_size)

    # ── Write ────────────────────────────────────────────────────────

    def upsert(self, doc_id: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        if self._client is None or self._model is None:
            return
        vec = self._model.encode(text).tolist()
        payload = {"text": text, **(metadata or {})}
        self._client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=doc_id, vector=vec, payload=payload)],
        )

    # ── Read ─────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        if self._client is None or self._model is None:
            log.warning("no-embeddings mode – returning empty results for query: %s", query[:80])
            return []
        vec = self._model.encode(query).tolist()
        hits = self._client.search(
            collection_name=self.collection,
            query_vector=vec,
            limit=top_k,
        )
        results: List[Dict[str, Any]] = []
        for h in hits:
            results.append(
                {
                    "source": (h.payload or {}).get("source", "unknown"),
                    "text": (h.payload or {}).get("text", ""),
                    "score": h.score,
                }
            )
        return results
