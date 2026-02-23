# RAG – Retrieval-Augmented Generation

## Overview

The RAG subsystem enriches the GenAI review and the Agent Controller decisions with contextual knowledge retrieved from an internal knowledge base. It relies on **Qdrant** (open-source vector database) and **sentence-transformers** (CPU-friendly embedding model) to provide semantic search over policies, runbooks, and risk rules.

## Architecture

```
docs/knowledge_base/*.md  ──►  POST /ingest  ──►  Qdrant (collection: tradeops_kb)
rag_corpus/*.md            ──►                        │
                                                      ▼
                           POST /query  ◄──  top-k passages + cosine scores
```

The **rag-api** service (port 8014) exposes two main endpoints and a health check.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe |
| `POST` | `/ingest` | Ingest `.md` / `.txt` files from a directory into Qdrant |
| `POST` | `/query` | Semantic search – returns top-k passages with similarity scores |

### POST /ingest

**Request body:**

```json
{
  "directory": "/app/rag_corpus"
}
```

**Response:**

```json
{
  "ingested": 5,
  "files": ["risk_rules.md", "runbook_kafka.md"]
}
```

### POST /query

**Request body:**

```json
{
  "question": "What is the maximum order size?",
  "top_k": 3
}
```

**Response:**

```json
{
  "hits": [
    {"source": "trading_policies.md", "text": "Maximum single order size: 10,000 units ...", "score": 0.8721}
  ]
}
```

## Embedding Model

The default model is `all-MiniLM-L6-v2` from the sentence-transformers library. It produces 384-dimensional vectors and runs efficiently on CPU. The model name is configurable via the `EMBEDDING_MODEL` environment variable.

## No-Embeddings Fallback

If `sentence-transformers` or `qdrant-client` is not installed (e.g. in CI), the service starts in **fallback mode**: `/health` returns OK, `/ingest` is a no-op, and `/query` returns an empty hit list with a warning log. This ensures the service never crashes due to missing ML dependencies.

## Knowledge Base

Documents are stored in two directories:

| Directory | Purpose |
|-----------|---------|
| `rag_corpus/` | Risk rules, Kafka runbook (existing) |
| `docs/knowledge_base/` | Trading policies, incident runbooks (new) |

To add new knowledge, simply drop `.md` or `.txt` files into either directory and call `POST /ingest`.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant server URL |
| `QDRANT_COLLECTION` | `tradeops_kb` | Collection name in Qdrant |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model name |
