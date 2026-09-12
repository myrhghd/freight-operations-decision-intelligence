from __future__ import annotations

from functools import lru_cache
from threading import Lock
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

from app.rag.ingest_docs import (
    CHROMA_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL_NAME,
    ingest_documents,
)


_embedding_model_lock = Lock()


@lru_cache(maxsize=1)
def _cached_embedding_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)


def get_embedding_model(model_name: str) -> SentenceTransformer:
    # Serialize the initial cache miss so concurrent requests do not load
    # multiple copies of the model into a memory constrained process.
    with _embedding_model_lock:
        return _cached_embedding_model(model_name)


def get_collection() -> chromadb.api.models.Collection.Collection:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DIR.as_posix())
    return client.get_or_create_collection(name=COLLECTION_NAME)


def retrieve_sop_chunks(question: str, top_k: int = 3) -> list[dict[str, Any]]:
    collection = get_collection()
    if collection.count() == 0:
        ingest_documents()
        collection = get_collection()

    model = get_embedding_model(EMBEDDING_MODEL_NAME)
    query_embedding = model.encode([question], show_progress_bar=False).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    chunks: list[dict[str, Any]] = []
    for document, metadata, distance in zip(documents, metadatas, distances):
        chunks.append(
            {
                "text": document,
                "source": metadata.get("source", "unknown.md"),
                "chunk_index": metadata.get("chunk_index", -1),
                "distance": distance,
            }
        )
    return chunks


def extractive_answer_from_chunks(question: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    if not chunks:
        return {"question": question, "answer": "No relevant SOP content found.", "sources": []}

    answer_parts = [str(chunk["text"]).strip() for chunk in chunks if str(chunk["text"]).strip()]
    combined_answer = "\n\n".join(answer_parts)
    sources = sorted({str(chunk["source"]) for chunk in chunks})

    return {
        "question": question,
        "answer": combined_answer,
        "sources": sources,
    }
