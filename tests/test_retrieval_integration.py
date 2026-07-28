from __future__ import annotations

from pathlib import Path

import pytest

import app.rag.ingest_docs as ingest_docs
import app.rag.retriever as retriever

pytestmark = pytest.mark.integration


@pytest.fixture
def isolated_sop_docs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ingestion and retrieval at a temporary docs folder and Chroma store.

    Uses the real Sentence Transformers model and a real Chroma collection so this
    test exercises the actual retrieval pipeline, not a mock. The embedding model is
    expected to already be cached locally by prior project setup.
    """
    docs_dir = tmp_path / "sample_sops"
    docs_dir.mkdir()
    (docs_dir / "weather_delay_policy.md").write_text(
        "# Weather Delay Policy\n\n"
        "If a shipment is delayed due to severe weather, notify the customer "
        "within two hours and provide a revised delivery estimate.\n"
    )
    chroma_dir = tmp_path / "chroma"

    monkeypatch.setattr(ingest_docs, "DOCS_DIR", docs_dir)
    monkeypatch.setattr(ingest_docs, "CHROMA_DIR", chroma_dir)
    monkeypatch.setattr(retriever, "CHROMA_DIR", chroma_dir)
    return docs_dir


def test_retrieve_sop_chunks_returns_matching_chunk(isolated_sop_docs: Path) -> None:
    chunks = retriever.retrieve_sop_chunks(
        question="What should I do for a weather delay?", top_k=1
    )
    assert len(chunks) == 1
    assert chunks[0]["source"] == "weather_delay_policy.md"
    assert "weather" in chunks[0]["text"].lower()
