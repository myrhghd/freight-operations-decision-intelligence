from __future__ import annotations

from app.db.connection import fetch_all, fetch_one


def get_shipment_details(shipment_id: str) -> dict | None:
    query = """
    SELECT
        s.shipment_id,
        s.shipment_status,
        s.shipment_mode,
        s.ship_date,
        s.planned_delivery_date,
        s.actual_delivery_date,
        s.is_delayed,
        s.delay_days,
        s.exception_flag,
        c.customer_name,
        c.customer_tier,
        ca.carrier_name,
        ca.carrier_type,
        r.origin_city,
        r.origin_state,
        r.destination_city,
        r.destination_state,
        r.distance_miles,
        s.freight_cost
    FROM shipments s
    JOIN customers c ON s.customer_id = c.customer_id
    JOIN carriers ca ON s.carrier_id = ca.carrier_id
    JOIN routes r ON s.route_id = r.route_id
    WHERE s.shipment_id = ?
    """
    return fetch_one(query, [shipment_id])


def get_shipment_events(shipment_id: str) -> list[dict]:
    query = """
    SELECT
        event_id,
        shipment_id,
        event_timestamp,
        event_type,
        event_city,
        event_state,
        event_description
    FROM shipment_events
    WHERE shipment_id = ?
    ORDER BY event_timestamp
    """
    return fetch_all(query, [shipment_id])


def get_delay_rates() -> list[dict]:
    query = """
    SELECT
        ca.carrier_name,
        r.origin_city,
        r.origin_state,
        r.destination_city,
        r.destination_state,
        COUNT(*) AS total_shipments,
        SUM(CASE WHEN s.is_delayed THEN 1 ELSE 0 END) AS delayed_shipments,
        ROUND(AVG(CASE WHEN s.is_delayed THEN 1.0 ELSE 0.0 END), 4) AS delay_rate,
        ROUND(AVG(CASE WHEN s.is_delayed THEN s.delay_days ELSE 0 END), 2) AS avg_delay_days
    FROM shipments s
    JOIN carriers ca ON s.carrier_id = ca.carrier_id
    JOIN routes r ON s.route_id = r.route_id
    GROUP BY
        ca.carrier_name,
        r.origin_city,
        r.origin_state,
        r.destination_city,
        r.destination_state
    ORDER BY delay_rate DESC, delayed_shipments DESC, total_shipments DESC
    """
    return fetch_all(query)


def get_high_risk_shipments(limit: int = 50) -> list[dict]:
    safe_limit = max(1, min(limit, 500))
    query = """
    SELECT
        s.shipment_id,
        s.shipment_status,
        c.customer_name,
        c.customer_tier,
        ca.carrier_name,
        r.origin_city,
        r.destination_city,
        s.planned_delivery_date,
        s.actual_delivery_date,
        s.is_delayed,
        s.delay_days,
        s.exception_flag,
        r.historical_delay_rate,
        CASE
            WHEN s.exception_flag AND s.is_delayed THEN 'Delayed with active exception'
            WHEN s.exception_flag THEN 'Shipment exception flagged'
            WHEN s.is_delayed THEN 'Shipment delivered late'
            WHEN r.historical_delay_rate >= 0.20 THEN 'Route has elevated historical delay rate'
            ELSE 'Monitoring risk'
        END AS risk_reason
    FROM shipments s
    JOIN customers c ON s.customer_id = c.customer_id
    JOIN carriers ca ON s.carrier_id = ca.carrier_id
    JOIN routes r ON s.route_id = r.route_id
    WHERE
        s.is_delayed = TRUE
        OR s.exception_flag = TRUE
        OR r.historical_delay_rate >= 0.20
    ORDER BY
        s.exception_flag DESC,
        s.is_delayed DESC,
        s.delay_days DESC,
        r.historical_delay_rate DESC
    LIMIT ?
    """
    return fetch_all(query, [safe_limit])
