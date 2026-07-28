from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence
from typing import Any

from app.db.connection import fetch_all, fetch_one
from app.graph import queries
from app.graph.connection import get_session
from app.graph.schema import apply_schema


BATCH_SIZE = 500

REFERENTIAL_CHECKS = {
    "shipments -> carriers": """
        SELECT COUNT(*) AS missing_count
        FROM shipments s
        LEFT JOIN carriers c ON s.carrier_id = c.carrier_id
        WHERE c.carrier_id IS NULL
    """,
    "shipments -> customers": """
        SELECT COUNT(*) AS missing_count
        FROM shipments s
        LEFT JOIN customers c ON s.customer_id = c.customer_id
        WHERE c.customer_id IS NULL
    """,
    "shipments -> routes": """
        SELECT COUNT(*) AS missing_count
        FROM shipments s
        LEFT JOIN routes r ON s.route_id = r.route_id
        WHERE r.route_id IS NULL
    """,
    "shipment_events -> shipments": """
        SELECT COUNT(*) AS missing_count
        FROM shipment_events e
        LEFT JOIN shipments s ON e.shipment_id = s.shipment_id
        WHERE s.shipment_id IS NULL
    """,
    "exceptions -> shipments": """
        SELECT COUNT(*) AS missing_count
        FROM exceptions x
        LEFT JOIN shipments s ON x.shipment_id = s.shipment_id
        WHERE s.shipment_id IS NULL
    """,
}


def validate_referential_integrity() -> None:
    """Confirm every foreign key in DuckDB resolves before creating graph relationships."""
    for label, query in REFERENTIAL_CHECKS.items():
        result = fetch_one(query)
        missing_count = result["missing_count"] if result else 0
        if missing_count:
            raise ValueError(f"Found {missing_count} unresolved reference(s) for {label}.")


def _batched(rows: Sequence[dict[str, Any]], batch_size: int = BATCH_SIZE) -> Iterator[Sequence[dict[str, Any]]]:
    for start in range(0, len(rows), batch_size):
        yield rows[start : start + batch_size]


def _fetch_carriers() -> list[dict[str, Any]]:
    return fetch_all(
        "SELECT carrier_id, carrier_name, carrier_type, on_time_rate, risk_score FROM carriers"
    )


def _fetch_customers() -> list[dict[str, Any]]:
    return fetch_all("SELECT customer_id, customer_name, customer_tier FROM customers")


def _fetch_routes() -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT route_id, origin_city, origin_state, destination_city, destination_state,
               historical_delay_rate
        FROM routes
        """
    )


def _fetch_shipments() -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT shipment_id, customer_id, carrier_id, route_id, shipment_status, shipment_mode,
               CAST(ship_date AS VARCHAR) AS ship_date,
               CAST(planned_delivery_date AS VARCHAR) AS planned_delivery_date,
               CAST(actual_delivery_date AS VARCHAR) AS actual_delivery_date,
               is_delayed, delay_days, exception_flag
        FROM shipments
        """
    )


def _fetch_shipment_events() -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT event_id, shipment_id, event_type,
               CAST(event_timestamp AS VARCHAR) AS event_timestamp,
               event_city, event_state
        FROM shipment_events
        """
    )


def _fetch_exceptions() -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT exception_id, shipment_id, exception_type, severity, resolution_status,
               CAST(detected_at AS VARCHAR) AS detected_at
        FROM exceptions
        """
    )


def run_ingestion() -> dict[str, int]:
    """Synchronize Neo4j with the current DuckDB tables. Deterministic and safe to run repeatedly.

    Every managed node and relationship is tagged with this run's id. Once all
    current rows have been merged, anything managed left over from a prior run
    (a row that no longer exists, or a relationship that pointed at an old
    reference) is removed. Cleanup only runs after ingestion succeeds, so a
    failed run never deletes data that was correct before it started.
    """
    validate_referential_integrity()
    run_id = str(uuid.uuid4())

    carriers = _fetch_carriers()
    customers = _fetch_customers()
    routes = _fetch_routes()
    shipments = _fetch_shipments()
    events = _fetch_shipment_events()
    exceptions = _fetch_exceptions()

    with get_session() as session:
        apply_schema(session)

        for batch in _batched(carriers):
            queries.merge_carriers(session, batch, run_id)
        for batch in _batched(customers):
            queries.merge_customers(session, batch, run_id)
        for batch in _batched(routes):
            queries.merge_routes(session, batch, run_id)
        for batch in _batched(shipments):
            queries.merge_shipments(session, batch, run_id)
        for batch in _batched(events):
            queries.merge_shipment_events(session, batch, run_id)
        for batch in _batched(exceptions):
            queries.merge_exceptions(session, batch, run_id)

        for batch in _batched(shipments):
            queries.merge_shipped_by(session, batch, run_id)
            queries.merge_shipped_for(session, batch, run_id)
            queries.merge_uses_route(session, batch, run_id)
        for batch in _batched(events):
            queries.merge_has_event(session, batch, run_id)
        for batch in _batched(exceptions):
            queries.merge_has_exception(session, batch, run_id)

        removed_relationships = queries.delete_stale_relationships(session, run_id)
        removed_nodes = queries.delete_stale_nodes(session, run_id)

    return {
        "carriers": len(carriers),
        "customers": len(customers),
        "routes": len(routes),
        "shipments": len(shipments),
        "shipment_events": len(events),
        "exceptions": len(exceptions),
        "removed_nodes": sum(removed_nodes.values()),
        "removed_relationships": sum(removed_relationships.values()),
    }


def main() -> None:
    counts = run_ingestion()
    print("Graph ingestion complete:")
    for label, count in counts.items():
        print(f"- {label}: {count:,}")


if __name__ == "__main__":
    main()
