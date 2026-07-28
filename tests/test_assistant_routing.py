from __future__ import annotations

import pytest

from app.services.assistant_service import build_chat_response

pytestmark = pytest.mark.usefixtures("use_test_database")

EXISTING_SHIPMENT_ID = "SHP-1001"


def test_shipment_status_question_routes_to_shipment_lookup() -> None:
    response = build_chat_response(f"What is the status of {EXISTING_SHIPMENT_ID}?")
    assert response["route"] == "shipment_lookup"
    assert response["data"]["shipment_id"] == EXISTING_SHIPMENT_ID


def test_shipment_events_question_routes_to_shipment_events() -> None:
    response = build_chat_response(f"Show me the timeline for {EXISTING_SHIPMENT_ID}")
    assert response["route"] == "shipment_events"
    assert len(response["data"]) > 0


def test_delay_analytics_question_routes_to_delay_analytics() -> None:
    response = build_chat_response("What are the delay rates by carrier and lane?")
    assert response["route"] == "delay_analytics"
    assert len(response["data"]) > 0


def test_high_risk_question_routes_to_high_risk_shipments() -> None:
    response = build_chat_response("Which shipments are high risk right now?")
    assert response["route"] == "high_risk_shipments"
    assert len(response["data"]) > 0


def test_sop_question_routes_to_vector_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.assistant_service.retrieve_sop_chunks",
        lambda question, top_k=3: [
            {
                "text": "Notify the customer within two hours of a confirmed delay.",
                "source": "customer_notification_policy.md",
                "chunk_index": 0,
                "distance": 0.1,
            }
        ],
    )
    response = build_chat_response("What is the customer notification policy?")
    assert response["route"] == "sop_search"
    assert response["sources"] == ["customer_notification_policy.md"]


def test_unsupported_question_falls_back_to_sop_search_with_no_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.assistant_service.retrieve_sop_chunks",
        lambda question, top_k=3: [],
    )
    response = build_chat_response("Tell me a joke about freight.")
    assert response["route"] == "sop_search"
    assert response["answer"] == "No relevant SOP content found."
    assert response["sources"] == []
