from __future__ import annotations

import pytest

import app.graph.connection as graph_connection
from app.services import graph_service
from app.services.assistant_service import build_chat_response, route_question

# require_neo4j pulls in the isolated neo4j-test service (see conftest.py). Tests
# that need DuckDB and graph data request `ingested_graph` directly, which syncs
# the same isolated synthetic dataset used across the graph test suite.
pytestmark = pytest.mark.usefixtures("require_neo4j")

EXISTING_SHIPMENT_ID = "SHP-1001"  # no recorded exception, has carrier/route peers
EXCEPTION_SHIPMENT_ID = "SHP-1021"  # has a "Missed appointment" exception and precedents
MISSING_SHIPMENT_ID = "SHP-9999"


# --- route selection ---


def test_why_question_routes_to_graph_shipment_explanation() -> None:
    question = f"Why is {EXISTING_SHIPMENT_ID} delayed?"
    assert route_question(question) == "graph_shipment_explanation"


def test_peer_question_routes_to_graph_peer_shipments() -> None:
    question = f"Which shipments share the same carrier and route as {EXISTING_SHIPMENT_ID}?"
    assert route_question(question) == "graph_peer_shipments"


def test_precedent_question_routes_to_graph_exception_precedents() -> None:
    question = f"Have we seen this exception before for {EXCEPTION_SHIPMENT_ID}?"
    assert route_question(question) == "graph_exception_precedents"


def test_procedure_question_routes_to_graph_sop_explanation() -> None:
    question = f"Which operating procedure applies to {EXCEPTION_SHIPMENT_ID}'s exception?"
    assert route_question(question) == "graph_sop_explanation"


def test_keyword_match_without_shipment_id_falls_back_to_sop_search() -> None:
    response = build_chat_response("Why is this shipment delayed?")
    assert response["route"] == "sop_search"


# --- connected shipment explanation (graph only) ---


def test_graph_shipment_explanation_returns_context_without_exception(
    ingested_graph: dict[str, int],
) -> None:
    response = build_chat_response(f"Why is {EXISTING_SHIPMENT_ID} delayed?")
    assert response["route"] == "graph_shipment_explanation"
    assert response["data"]["shipment"]["shipment_id"] == EXISTING_SHIPMENT_ID
    assert response["data"]["graph_context"] is not None
    assert response["data"]["graph_context"]["exception"] is None
    assert response["retrieval_sources"] == ["duckdb", "neo4j"]


def test_graph_shipment_explanation_reports_exception_when_present(
    ingested_graph: dict[str, int],
) -> None:
    response = build_chat_response(f"Why is {EXCEPTION_SHIPMENT_ID} delayed?")
    assert response["route"] == "graph_shipment_explanation"
    exception = response["data"]["graph_context"]["exception"]
    assert exception is not None
    assert exception["exception_type"] == "Missed appointment"


# --- peer shipment retrieval (graph only) ---


def test_graph_peer_shipments_returns_peers(ingested_graph: dict[str, int]) -> None:
    question = f"Which shipments share the same carrier and route as {EXISTING_SHIPMENT_ID}?"
    response = build_chat_response(question)
    assert response["route"] == "graph_peer_shipments"
    peers = response["data"]["peers"]
    assert len(peers) > 0
    assert all(peer["shipment_id"] != EXISTING_SHIPMENT_ID for peer in peers)
    assert response["retrieval_sources"] == ["duckdb", "neo4j"]


def test_graph_peer_shipments_empty_result(
    ingested_graph: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.services.assistant_service.get_peer_shipments",
        lambda shipment_id, limit=10: ([], None),
    )
    question = f"Which shipments share the same carrier and route as {EXISTING_SHIPMENT_ID}?"
    response = build_chat_response(question)
    assert response["data"]["peers"] == []
    assert "no other shipments" in response["answer"].lower()
    assert "neo4j" in response["retrieval_sources"]


# --- exception precedent retrieval (graph only) ---


def test_graph_exception_precedents_returns_precedents(ingested_graph: dict[str, int]) -> None:
    question = f"Have we seen this exception before for {EXCEPTION_SHIPMENT_ID}?"
    response = build_chat_response(question)
    assert response["route"] == "graph_exception_precedents"
    precedents = response["data"]["precedents"]
    assert len(precedents) > 0
    assert all(item["shipment_id"] != EXCEPTION_SHIPMENT_ID for item in precedents)
    assert response["retrieval_sources"] == ["duckdb", "neo4j"]


def test_graph_exception_precedents_shipment_without_exception(
    ingested_graph: dict[str, int],
) -> None:
    question = f"Have we seen this exception before for {EXISTING_SHIPMENT_ID}?"
    response = build_chat_response(question)
    assert response["route"] == "graph_exception_precedents"
    assert response["data"]["precedents"] == []
    assert "no recorded exception" in response["answer"].lower()
    assert response["retrieval_sources"] == ["duckdb"]


def test_graph_exception_precedents_empty_result(
    ingested_graph: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.services.assistant_service.get_exception_precedents",
        lambda shipment_id, limit=10: ([], None),
    )
    question = f"Have we seen this exception before for {EXCEPTION_SHIPMENT_ID}?"
    response = build_chat_response(question)
    assert response["data"]["precedents"] == []
    assert "no prior shipments" in response["answer"].lower()


# --- SOP retrieval using the confirmed exception type (graph then Chroma) ---


def test_graph_sop_explanation_uses_confirmed_exception_type(
    ingested_graph: dict[str, int],
) -> None:
    question = f"Which operating procedure applies to {EXCEPTION_SHIPMENT_ID}'s exception?"
    response = build_chat_response(question)
    assert response["route"] == "graph_sop_explanation"
    assert response["data"]["sop_guidance"] is not None
    assert len(response["data"]["sop_guidance"]["sources"]) > 0
    assert response["retrieval_sources"] == ["duckdb", "neo4j", "chroma"]


def test_graph_sop_explanation_skips_chroma_without_exception(
    ingested_graph: dict[str, int],
) -> None:
    question = f"Which operating procedure applies to {EXISTING_SHIPMENT_ID}'s exception?"
    response = build_chat_response(question)
    assert response["data"]["sop_guidance"] is None
    assert "chroma" not in response["retrieval_sources"]
    assert "no recorded exception" in response["answer"].lower()


# --- missing shipment ID ---


def test_graph_route_missing_shipment_id_returns_clear_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.assistant_service.route_question",
        lambda question: "graph_shipment_explanation",
    )
    response = build_chat_response("Why is this delayed?")
    assert response["route"] == "graph_shipment_explanation"
    assert response["data"]["shipment"] is None
    assert response["answer"] == "No shipment ID found in the question."
    assert response["retrieval_sources"] == []


# --- unknown shipment ---


@pytest.mark.parametrize(
    "question",
    [
        f"Why is {MISSING_SHIPMENT_ID} delayed?",
        f"Which shipments share the same carrier and route as {MISSING_SHIPMENT_ID}?",
        f"Have we seen this exception before for {MISSING_SHIPMENT_ID}?",
        f"Which operating procedure applies to {MISSING_SHIPMENT_ID}'s exception?",
    ],
)
def test_graph_routes_unknown_shipment(question: str, ingested_graph: dict[str, int]) -> None:
    response = build_chat_response(question)
    assert response["data"]["shipment"] is None
    assert f"'{MISSING_SHIPMENT_ID}' was not found" in response["answer"]
    assert response["retrieval_sources"] == []


# --- Neo4j unavailable ---


def test_graph_shipment_explanation_neo4j_unavailable(
    ingested_graph: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.services.assistant_service.get_shipment_graph_context",
        lambda shipment_id: (None, "Neo4j is currently unavailable."),
    )
    response = build_chat_response(f"Why is {EXISTING_SHIPMENT_ID} delayed?")
    assert response["data"]["graph_context"] is None
    assert "unavailable" in response["answer"].lower()
    assert response["retrieval_sources"] == ["duckdb"]


def test_graph_peer_shipments_neo4j_unavailable(
    ingested_graph: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.services.assistant_service.get_peer_shipments",
        lambda shipment_id, limit=10: ([], "Neo4j is currently unavailable."),
    )
    question = f"Which shipments share the same carrier and route as {EXISTING_SHIPMENT_ID}?"
    response = build_chat_response(question)
    assert "unavailable" in response["answer"].lower()
    assert response["retrieval_sources"] == ["duckdb"]


def test_graph_sop_explanation_neo4j_unavailable(
    ingested_graph: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.services.assistant_service.get_shipment_graph_context",
        lambda shipment_id: (None, "Neo4j is currently unavailable."),
    )
    question = f"Which operating procedure applies to {EXCEPTION_SHIPMENT_ID}'s exception?"
    response = build_chat_response(question)
    assert response["data"]["sop_guidance"] is None
    assert "unavailable" in response["answer"].lower()
    assert response["retrieval_sources"] == ["duckdb"]


def test_graph_service_reports_unavailable_for_unreachable_neo4j() -> None:
    """Exercise graph_service's own try/except against a genuinely unreachable Neo4j."""
    original_uri = graph_connection.NEO4J_URI
    graph_connection.close_driver()
    graph_connection.NEO4J_URI = "bolt://localhost:1"
    try:
        context, error = graph_service.get_shipment_graph_context(EXISTING_SHIPMENT_ID)
        assert context is None
        assert error == graph_service.GRAPH_UNAVAILABLE_ERROR
    finally:
        graph_connection.close_driver()
        graph_connection.NEO4J_URI = original_uri


# --- Chroma unavailable ---


def test_graph_sop_explanation_chroma_unavailable(
    ingested_graph: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise_chroma_error(question: str, top_k: int = 3):
        raise RuntimeError("Chroma is unavailable")

    monkeypatch.setattr(
        "app.services.assistant_service.retrieve_sop_chunks", _raise_chroma_error
    )
    question = f"Which operating procedure applies to {EXCEPTION_SHIPMENT_ID}'s exception?"
    response = build_chat_response(question)
    assert response["data"]["sop_guidance"] is None
    assert "unavailable" in response["answer"].lower()
    assert response["retrieval_sources"] == ["duckdb", "neo4j"]


# --- existing routes remain unchanged ---


def test_existing_shipment_lookup_route_and_shape_unchanged(
    ingested_graph: dict[str, int],
) -> None:
    response = build_chat_response(f"What is the status of {EXISTING_SHIPMENT_ID}?")
    assert response["route"] == "shipment_lookup"
    assert set(response.keys()) == {"question", "route", "answer", "data", "sources"}
    assert response["data"]["shipment_id"] == EXISTING_SHIPMENT_ID


def test_existing_sop_search_route_and_shape_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.assistant_service.retrieve_sop_chunks",
        lambda question, top_k=3: [],
    )
    response = build_chat_response("Tell me a joke about freight.")
    assert response["route"] == "sop_search"
    assert set(response.keys()) == {"question", "route", "answer", "data", "sources"}
