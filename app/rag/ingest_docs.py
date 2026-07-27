from __future__ import annotations

import re
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from app.core.config import PROJECT_ROOT


DOCS_DIR = PROJECT_ROOT / "data" / "sample_sops"
CHROMA_DIR = PROJECT_ROOT / "data" / "processed" / "chroma"
COLLECTION_NAME = "sop_faq_docs"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MAX_CHUNK_CHARS = 900


def split_large_chunk(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if not sentence.strip():
            continue
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = sentence.strip()
    if current:
        chunks.append(current)
    return chunks


def chunk_markdown(content: str) -> list[str]:
    sections = re.split(r"\n(?=#)", content)
    chunks: list[str] = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        paragraphs = [p.strip() for p in section.split("\n\n") if p.strip()]
        for paragraph in paragraphs:
            chunks.extend(split_large_chunk(paragraph))
    return chunks


def load_markdown_chunks() -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    for filepath in sorted(DOCS_DIR.glob("*.md")):
        content = filepath.read_text(encoding="utf-8")
        chunks = chunk_markdown(content)
        for idx, chunk_text in enumerate(chunks):
            rows.append(
                {
                    "id": f"{filepath.stem}-{idx}",
                    "text": chunk_text,
                    "source": filepath.name,
                    "chunk_index": idx,
                }
            )
    return rows


def ingest_documents() -> int:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DIR.as_posix())
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    rows = load_markdown_chunks()
    if not rows:
        return 0

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    texts = [str(row["text"]) for row in rows]
    embeddings = model.encode(texts, show_progress_bar=False).tolist()

    ids = [str(row["id"]) for row in rows]
    metadatas = [
        {"source": str(row["source"]), "chunk_index": int(row["chunk_index"])}
        for row in rows
    ]

    existing = collection.get(include=[])
    existing_ids = existing.get("ids", [])
    if existing_ids:
        collection.delete(ids=existing_ids)
    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    return len(rows)


def main() -> None:
    count = ingest_documents()
    print(f"Ingested {count} SOP/FAQ chunks into {CHROMA_DIR}")


if __name__ == "__main__":
    main()
