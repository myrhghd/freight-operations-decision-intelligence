from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

pytestmark = pytest.mark.usefixtures("require_neo4j")

EXISTING_SHIPMENT_ID = "SHP-1001"
EXCEPTION_SHIPMENT_ID = "SHP-1021"
MISSING_SHIPMENT_ID = "SHP-9999"


@pytest.fixture
def client(ingested_graph: dict[str, int]) -> TestClient:
    return TestClient(app)


def test_graph_shipment_explanation_endpoint(client: TestClient) -> None:
    response = client.post(
        "/assistant/chat", json={"question": f"Why is {EXISTING_SHIPMENT_ID} delayed?"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "graph_shipment_explanation"
    assert body["data"]["shipment"]["shipment_id"] == EXISTING_SHIPMENT_ID
    assert "neo4j" in body["retrieval_sources"]


def test_graph_peer_shipments_endpoint(client: TestClient) -> None:
    question = f"Which shipments share the same carrier and route as {EXISTING_SHIPMENT_ID}?"
    response = client.post("/assistant/chat", json={"question": question})
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "graph_peer_shipments"
    assert len(body["data"]["peers"]) > 0


def test_graph_exception_precedents_endpoint(client: TestClient) -> None:
    question = f"Have we seen this exception before for {EXCEPTION_SHIPMENT_ID}?"
    response = client.post("/assistant/chat", json={"question": question})
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "graph_exception_precedents"
    assert len(body["data"]["precedents"]) > 0


def test_graph_sop_explanation_endpoint(client: TestClient) -> None:
    question = f"Which operating procedure applies to {EXCEPTION_SHIPMENT_ID}'s exception?"
    response = client.post("/assistant/chat", json={"question": question})
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "graph_sop_explanation"
    assert body["data"]["sop_guidance"] is not None
    assert "chroma" in body["retrieval_sources"]


def test_graph_exception_precedents_shipment_without_exception_endpoint(
    client: TestClient,
) -> None:
    question = f"Have we seen this exception before for {EXISTING_SHIPMENT_ID}?"
    response = client.post("/assistant/chat", json={"question": question})
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["precedents"] == []
    assert "no recorded exception" in body["answer"].lower()


def test_graph_route_unknown_shipment_endpoint(client: TestClient) -> None:
    response = client.post(
        "/assistant/chat", json={"question": f"Why is {MISSING_SHIPMENT_ID} delayed?"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["shipment"] is None
    assert f"'{MISSING_SHIPMENT_ID}' was not found" in body["answer"]


def test_existing_shipment_endpoint_and_missing_shipment_behavior_unchanged(
    client: TestClient,
) -> None:
    response = client.get(f"/shipments/{EXISTING_SHIPMENT_ID}")
    assert response.status_code == 200
    assert response.json()["shipment_id"] == EXISTING_SHIPMENT_ID

    response = client.get(f"/shipments/{MISSING_SHIPMENT_ID}")
    assert response.status_code == 404


def test_existing_assistant_chat_shipment_lookup_unchanged(client: TestClient) -> None:
    response = client.post(
        "/assistant/chat", json={"question": f"What is the status of {EXISTING_SHIPMENT_ID}?"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "shipment_lookup"
    assert body["data"]["shipment_id"] == EXISTING_SHIPMENT_ID
    assert set(body.keys()) == {"question", "route", "answer", "data", "sources"}


def test_health_endpoint_still_independent_of_graph_route_changes(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
