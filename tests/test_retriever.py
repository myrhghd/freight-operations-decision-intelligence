import runpy
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

from app.rag import retriever


@pytest.fixture
def mocked_retrieval(monkeypatch):
    retriever._cached_embedding_model.cache_clear()
    model = Mock()
    model.encode.return_value.tolist.return_value = [[0.1, 0.2]]
    constructor = Mock(return_value=model)
    monkeypatch.setattr(retriever, "SentenceTransformer", constructor)
    collection = Mock()
    collection.count.return_value = 1
    collection.query.return_value = {
        "documents": [["Notify the customer."]],
        "metadatas": [[{"source": "weather.md", "chunk_index": 2}]],
        "distances": [[0.15]],
    }
    monkeypatch.setattr(retriever, "get_collection", Mock(return_value=collection))
    yield constructor, model, collection
    retriever._cached_embedding_model.cache_clear()


def test_import_does_not_initialize_model(monkeypatch):
    constructor = Mock(side_effect=AssertionError("Model initialized during import"))
    monkeypatch.setattr("sentence_transformers.SentenceTransformer", constructor)
    runpy.run_path(retriever.__file__)
    constructor.assert_not_called()


def test_queries_reuse_model_and_preserve_retrieval(mocked_retrieval):
    constructor, model, collection = mocked_retrieval
    expected = [{"text": "Notify the customer.", "source": "weather.md",
                 "chunk_index": 2, "distance": 0.15}]
    for question in ("Weather procedure?", "Customer notification?"):
        assert retriever.retrieve_sop_chunks(question, top_k=1) == expected
        model.encode.assert_called_with([question], show_progress_bar=False)
        collection.query.assert_called_with(query_embeddings=[[0.1, 0.2]], n_results=1,
                                            include=["documents", "metadatas", "distances"])
    constructor.assert_called_once_with(retriever.EMBEDDING_MODEL_NAME)
    assert model.encode.call_count == 2


def test_cache_is_keyed_by_model_name(mocked_retrieval):
    constructor, _, _ = mocked_retrieval
    retriever.get_embedding_model("model-a")
    retriever.get_embedding_model("model-a")
    retriever.get_embedding_model("model-b")
    assert constructor.call_count == 2
    constructor.assert_called_with("model-b")


def test_concurrent_cold_requests_initialize_once(mocked_retrieval):
    constructor, model, _ = mocked_retrieval
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(retriever.get_embedding_model, ["model-a"] * 8))
    assert all(result is model for result in results)
    constructor.assert_called_once_with("model-a")


def test_failed_initialization_is_not_cached(mocked_retrieval):
    constructor, model, _ = mocked_retrieval
    constructor.side_effect = [RuntimeError("load failed"), model]
    with pytest.raises(RuntimeError):
        retriever.get_embedding_model("model-a")
    assert retriever.get_embedding_model("model-a") is model
    assert constructor.call_count == 2


def test_explicit_cache_clear_preserves_test_isolation(mocked_retrieval):
    constructor, _, _ = mocked_retrieval
    retriever.get_embedding_model("model-a")
    retriever._cached_embedding_model.cache_clear()
    replacement = Mock()
    constructor.return_value = replacement
    assert retriever.get_embedding_model("model-a") is replacement


def test_empty_collection_still_ingests_and_reopens(mocked_retrieval, monkeypatch):
    _, _, collection = mocked_retrieval
    collection.count.return_value = 0
    ingest = Mock()
    monkeypatch.setattr(retriever, "ingest_documents", ingest)
    retriever.retrieve_sop_chunks("Weather procedure?")
    ingest.assert_called_once_with()
    assert retriever.get_collection.call_count == 2


def test_chroma_paths_and_collection_names_remain_dynamic(tmp_path, monkeypatch):
    client = Mock()
    factory = Mock(return_value=client)
    monkeypatch.setattr(retriever.chromadb, "PersistentClient", factory)
    for name in ("first", "second"):
        path = tmp_path / name
        monkeypatch.setattr(retriever, "CHROMA_DIR", path)
        monkeypatch.setattr(retriever, "COLLECTION_NAME", name)
        assert retriever.get_collection() is client.get_or_create_collection.return_value
        factory.assert_called_with(path=path.as_posix())
        client.get_or_create_collection.assert_called_with(name=name)
