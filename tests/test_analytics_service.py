from __future__ import annotations

import pytest

from app.services.shipment_service import get_delay_rates, get_high_risk_shipments

pytestmark = pytest.mark.usefixtures("use_test_database")


def test_get_delay_rates_has_expected_structure() -> None:
    rows = get_delay_rates()
    assert len(rows) > 0

    expected_keys = {
        "carrier_name",
        "origin_city",
        "origin_state",
        "destination_city",
        "destination_state",
        "total_shipments",
        "delayed_shipments",
        "delay_rate",
        "avg_delay_days",
    }
    for row in rows:
        assert expected_keys.issubset(row.keys())
        assert row["total_shipments"] >= row["delayed_shipments"] >= 0


def test_get_high_risk_shipments_has_expected_structure() -> None:
    rows = get_high_risk_shipments(limit=10)
    assert 0 < len(rows) <= 10

    expected_keys = {
        "shipment_id",
        "shipment_status",
        "risk_reason",
        "is_delayed",
        "exception_flag",
    }
    for row in rows:
        assert expected_keys.issubset(row.keys())
        assert row["is_delayed"] or row["exception_flag"] or row["historical_delay_rate"] >= 0.20


def test_get_high_risk_shipments_clamps_limit_below_minimum() -> None:
    rows = get_high_risk_shipments(limit=0)
    assert len(rows) == 1


def test_get_high_risk_shipments_clamps_limit_above_maximum() -> None:
    rows = get_high_risk_shipments(limit=10_000)
    assert len(rows) <= 500
