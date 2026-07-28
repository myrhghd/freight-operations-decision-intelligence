from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

pytestmark = pytest.mark.usefixtures("use_test_database")

EXISTING_SHIPMENT_ID = "SHP-1001"
MISSING_SHIPMENT_ID = "SHP-9999"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_shipment_endpoint(client: TestClient) -> None:
    response = client.get(f"/shipments/{EXISTING_SHIPMENT_ID}")
    assert response.status_code == 200
    assert response.json()["shipment_id"] == EXISTING_SHIPMENT_ID


def test_get_shipment_endpoint_missing_shipment_returns_404(client: TestClient) -> None:
    response = client.get(f"/shipments/{MISSING_SHIPMENT_ID}")
    assert response.status_code == 404


def test_high_risk_shipments_endpoint(client: TestClient) -> None:
    response = client.get("/analytics/high-risk-shipments", params={"limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert 0 < len(body) <= 5


def test_assistant_chat_endpoint(client: TestClient) -> None:
    response = client.post(
        "/assistant/chat", json={"question": f"What is the status of {EXISTING_SHIPMENT_ID}?"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "shipment_lookup"
    assert body["data"]["shipment_id"] == EXISTING_SHIPMENT_ID
