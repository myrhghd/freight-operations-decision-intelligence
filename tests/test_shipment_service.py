from __future__ import annotations

import pytest

from app.services.shipment_service import get_shipment_details, get_shipment_events

pytestmark = pytest.mark.usefixtures("use_test_database")

EXISTING_SHIPMENT_ID = "SHP-1001"
MISSING_SHIPMENT_ID = "SHP-9999"


def test_get_shipment_details_returns_expected_fields() -> None:
    shipment = get_shipment_details(EXISTING_SHIPMENT_ID)
    assert shipment is not None
    assert shipment["shipment_id"] == EXISTING_SHIPMENT_ID
    for field in ("customer_name", "carrier_name", "origin_city", "destination_city"):
        assert field in shipment


def test_get_shipment_details_missing_shipment_returns_none() -> None:
    assert get_shipment_details(MISSING_SHIPMENT_ID) is None


def test_get_shipment_events_returns_events_in_chronological_order() -> None:
    events = get_shipment_events(EXISTING_SHIPMENT_ID)
    assert len(events) > 0
    timestamps = [event["event_timestamp"] for event in events]
    assert timestamps == sorted(timestamps)


def test_get_shipment_events_missing_shipment_returns_empty_list() -> None:
    assert get_shipment_events(MISSING_SHIPMENT_ID) == []
