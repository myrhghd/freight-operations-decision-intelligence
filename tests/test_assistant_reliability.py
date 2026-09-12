from __future__ import annotations

import pytest

from app.services.assistant_service import build_chat_response, route_question

pytestmark = pytest.mark.usefixtures("use_test_database")

EXISTING_SHIPMENT_ID = "SHP-1001"


# --- conflicting route phrases (documented, regression locked precedence) ---


@pytest.mark.parametrize(
    ("question", "expected_route"),
    [
        (f"What is the escalation status for {EXISTING_SHIPMENT_ID}?", "shipment_lookup"),
        (f"Which policy applies to the events for {EXISTING_SHIPMENT_ID}?", "shipment_events"),
        (f"Why is the delay rate high for {EXISTING_SHIPMENT_ID}?", "graph_shipment_explanation"),
        (
            f"What is the carrier performance and risk for {EXISTING_SHIPMENT_ID}?",
            "delay_analytics",
        ),
        (f"What is the status and timeline for {EXISTING_SHIPMENT_ID}?", "shipment_lookup"),
        (f"Where is {EXISTING_SHIPMENT_ID} and why is it delayed?", "shipment_lookup"),
    ],
)
def test_conflicting_route_phrases_resolve_to_documented_precedence(
    question: str, expected_route: str
) -> None:
    assert route_question(question) == expected_route


def test_singular_and_plural_exception_precedent_phrasing_both_route_correctly() -> None:
    singular = f"Have we seen this exception before for {EXISTING_SHIPMENT_ID}?"
    plural = f"Have we seen this exceptions before for {EXISTING_SHIPMENT_ID}?"
    assert route_question(singular) == "graph_exception_precedents"
    assert route_question(plural) == "graph_exception_precedents"


# --- existing SOP route when Chroma is unavailable ---


def test_sop_search_degrades_gracefully_when_chroma_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_chroma_error(question: str, top_k: int = 3):
        raise RuntimeError("Chroma is unavailable")

    monkeypatch.setattr(
        "app.services.assistant_service.retrieve_sop_chunks", _raise_chroma_error
    )
    response = build_chat_response("What is the customer notification policy?")

    assert response["route"] == "sop_search"
    assert response["answer"] == "SOP retrieval is currently unavailable."
    assert response["data"] == []
    assert response["sources"] == []
    assert set(response.keys()) == {"question", "route", "answer", "data", "sources"}


# --- existing routes remain unchanged ---


def test_shipment_lookup_route_shape_unchanged() -> None:
    response = build_chat_response(f"What is the status of {EXISTING_SHIPMENT_ID}?")
    assert response["route"] == "shipment_lookup"
    assert set(response.keys()) == {"question", "route", "answer", "data", "sources"}
    assert response["data"]["shipment_id"] == EXISTING_SHIPMENT_ID


def test_shipment_events_route_shape_unchanged() -> None:
    response = build_chat_response(f"Show me the timeline for {EXISTING_SHIPMENT_ID}")
    assert response["route"] == "shipment_events"
    assert set(response.keys()) == {"question", "route", "answer", "data", "sources"}


def test_delay_analytics_route_shape_unchanged() -> None:
    response = build_chat_response("What are the delay rates by carrier and lane?")
    assert response["route"] == "delay_analytics"
    assert set(response.keys()) == {"question", "route", "answer", "data", "sources"}


def test_high_risk_shipments_route_shape_unchanged() -> None:
    response = build_chat_response("Which shipments are high risk right now?")
    assert response["route"] == "high_risk_shipments"
    assert set(response.keys()) == {"question", "route", "answer", "data", "sources"}


def test_sop_search_route_shape_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.assistant_service.retrieve_sop_chunks",
        lambda question, top_k=3: [
            {"text": "Notify the customer.", "source": "weather_delay_policy.md",
             "chunk_index": 0, "distance": 0.1}
        ],
    )
    response = build_chat_response("What is the weather delay policy?")
    assert response["route"] == "sop_search"
    assert set(response.keys()) == {"question", "route", "answer", "data", "sources"}
