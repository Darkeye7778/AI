from __future__ import annotations

import hashlib
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from assistant.config import settings

_collection: Any = None
_embedder: Any = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(settings.embedding_model)
    return _embedder


def _get_collection():
    global _collection
    if _collection is None:
        settings.chroma_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(
            path=str(settings.chroma_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = client.get_or_create_collection(
            name="memories",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def embed_text(text: str) -> list[float]:
    return _get_embedder().encode(text, normalize_embeddings=True).tolist()


def index_memory(
    memory_id: str,
    content: str,
    category: str,
    title: str = "",
    source: str = "manual",
) -> None:
    collection = _get_collection()
    doc_id = hashlib.md5(memory_id.encode()).hexdigest()
    collection.upsert(
        ids=[doc_id],
        documents=[content],
        embeddings=[embed_text(content)],
        metadatas=[{
            "memory_id": memory_id,
            "category": category,
            "title": title,
            "source": source,
        }],
    )


def search_memories(
    query: str,
    limit: int = 8,
    categories: list[str] | None = None,
) -> list[dict]:
    collection = _get_collection()
    if collection.count() == 0:
        return []

    where = {"category": {"$in": categories}} if categories else None
    results = collection.query(
        query_embeddings=[embed_text(query)],
        n_results=min(limit, collection.count()),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append({
            "memory_id": meta["memory_id"],
            "category": meta["category"],
            "title": meta.get("title", ""),
            "content": doc,
            "score": 1 - dist,
            "source": meta.get("source", ""),
        })
    return sorted(hits, key=lambda h: h["score"], reverse=True)


def delete_memory_index(memory_id: str) -> None:
    collection = _get_collection()
    doc_id = hashlib.md5(memory_id.encode()).hexdigest()
    try:
        collection.delete(ids=[doc_id])
    except Exception:
        pass