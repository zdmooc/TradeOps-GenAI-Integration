"""RAG API – FastAPI service backed by Qdrant (vector DB).

Provides:
  POST /ingest  – ingest documents from docs/knowledge_base/* or rag_corpus/*
  POST /query   – semantic search returning top-k passages + scores
  GET  /health  – liveness / readiness probe
"""

import os
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from services.common.logging import setup_logging
from services.common.metrics import install
from services.rag_api.vectorstore import VectorStore

log = setup_logging("rag-api")

app = FastAPI(title="RAG API", version="0.1")
install(app, "rag-api")

# Global vector store instance – initialised on startup
_store: Optional[VectorStore] = None


@app.on_event("startup")
async def _startup():
    global _store
    qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
    collection = os.getenv("QDRANT_COLLECTION", "tradeops_kb")
    embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    _store = VectorStore(
        qdrant_url=qdrant_url,
        collection=collection,
        embedding_model=embedding_model,
    )
    _store.ensure_collection()
    log.info(
        "VectorStore ready qdrant=%s collection=%s model=%s",
        qdrant_url,
        collection,
        embedding_model,
    )


# ── Schemas ──────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    directory: str = Field(
        default="/app/rag_corpus",
        description="Path inside the container to scan for .md / .txt files",
    )


class IngestResponse(BaseModel):
    ingested: int
    files: List[str]


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=3, ge=1, le=20)


class PassageHit(BaseModel):
    source: str
    text: str
    score: float


class QueryResponse(BaseModel):
    hits: List[PassageHit]


# ── Endpoints ────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "rag-api"}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(
        generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest):
    """Ingest markdown / text files from a directory into Qdrant."""
    assert _store is not None
    base = Path(req.directory)
    if not base.is_dir():
        raise HTTPException(400, f"directory not found: {req.directory}")

    files_ingested: List[str] = []
    total = 0
    for fp in sorted(base.rglob("*")):
        if fp.suffix.lower() not in (".md", ".txt"):
            continue
        text = fp.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        chunks = _chunk_text(text, max_tokens=256)
        for i, chunk in enumerate(chunks):
            doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{fp.name}:{i}"))
            _store.upsert(doc_id=doc_id, text=chunk, metadata={"source": fp.name, "chunk": i})
            total += 1
        files_ingested.append(fp.name)

    log.info("ingested %d chunks from %d files", total, len(files_ingested))
    return IngestResponse(ingested=total, files=files_ingested)


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    """Semantic search over the knowledge base."""
    assert _store is not None
    results = _store.search(req.question, top_k=req.top_k)
    hits = [
        PassageHit(source=r["source"], text=r["text"], score=round(r["score"], 4))
        for r in results
    ]
    return QueryResponse(hits=hits)


# ── Helpers ──────────────────────────────────────────────────────────

def _chunk_text(text: str, max_tokens: int = 256) -> List[str]:
    """Naive sentence-boundary chunking (good enough for demo)."""
    words = text.split()
    chunks: List[str] = []
    buf: List[str] = []
    for w in words:
        buf.append(w)
        if len(buf) >= max_tokens:
            chunks.append(" ".join(buf))
            buf = []
    if buf:
        chunks.append(" ".join(buf))
    return chunks
