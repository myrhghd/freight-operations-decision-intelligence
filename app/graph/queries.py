from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from neo4j import Session


MANAGED_NODE_LABELS = ["Shipment", "Carrier", "Customer", "Route", "ShipmentEvent", "Exception"]
MANAGED_RELATIONSHIP_TYPES = [
    "SHIPPED_BY",
    "SHIPPED_FOR",
    "USES_ROUTE",
    "HAS_EVENT",
    "HAS_EXCEPTION",
]

# Marks a node or relationship as owned by the DuckDB ingestion pipeline, as opposed
# to any unmanaged record that might exist in the graph for other reasons.
MANAGED_SOURCE = "duckdb"


def merge_carriers(session: Session, rows: Sequence[dict[str, Any]], run_id: str) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MERGE (c:Carrier {carrier_id: row.carrier_id})
        SET c.carrier_name = row.carrier_name,
            c.carrier_type = row.carrier_type,
            c.on_time_rate = row.on_time_rate,
            c.risk_score = row.risk_score,
            c._source = $source,
            c._run_id = $run_id
        """,
        rows=rows,
        source=MANAGED_SOURCE,
        run_id=run_id,
    ).consume()


def merge_customers(session: Session, rows: Sequence[dict[str, Any]], run_id: str) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MERGE (c:Customer {customer_id: row.customer_id})
        SET c.customer_name = row.customer_name,
            c.customer_tier = row.customer_tier,
            c._source = $source,
            c._run_id = $run_id
        """,
        rows=rows,
        source=MANAGED_SOURCE,
        run_id=run_id,
    ).consume()


def merge_routes(session: Session, rows: Sequence[dict[str, Any]], run_id: str) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MERGE (r:Route {route_id: row.route_id})
        SET r.origin_city = row.origin_city,
            r.origin_state = row.origin_state,
            r.destination_city = row.destination_city,
            r.destination_state = row.destination_state,
            r.historical_delay_rate = row.historical_delay_rate,
            r._source = $source,
            r._run_id = $run_id
        """,
        rows=rows,
        source=MANAGED_SOURCE,
        run_id=run_id,
    ).consume()


def merge_shipments(session: Session, rows: Sequence[dict[str, Any]], run_id: str) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MERGE (s:Shipment {shipment_id: row.shipment_id})
        SET s.shipment_status = row.shipment_status,
            s.shipment_mode = row.shipment_mode,
            s.ship_date = row.ship_date,
            s.planned_delivery_date = row.planned_delivery_date,
            s.actual_delivery_date = row.actual_delivery_date,
            s.is_delayed = row.is_delayed,
            s.delay_days = row.delay_days,
            s.exception_flag = row.exception_flag,
            s._source = $source,
            s._run_id = $run_id
        """,
        rows=rows,
        source=MANAGED_SOURCE,
        run_id=run_id,
    ).consume()


def merge_shipment_events(session: Session, rows: Sequence[dict[str, Any]], run_id: str) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MERGE (e:ShipmentEvent {event_id: row.event_id})
        SET e.event_type = row.event_type,
            e.event_timestamp = row.event_timestamp,
            e.event_city = row.event_city,
            e.event_state = row.event_state,
            e._source = $source,
            e._run_id = $run_id
        """,
        rows=rows,
        source=MANAGED_SOURCE,
        run_id=run_id,
    ).consume()


def merge_exceptions(session: Session, rows: Sequence[dict[str, Any]], run_id: str) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MERGE (x:Exception {exception_id: row.exception_id})
        SET x.exception_type = row.exception_type,
            x.severity = row.severity,
            x.resolution_status = row.resolution_status,
            x.detected_at = row.detected_at,
            x._source = $source,
            x._run_id = $run_id
        """,
        rows=rows,
        source=MANAGED_SOURCE,
        run_id=run_id,
    ).consume()


def merge_shipped_by(session: Session, rows: Sequence[dict[str, Any]], run_id: str) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MATCH (s:Shipment {shipment_id: row.shipment_id})
        MATCH (c:Carrier {carrier_id: row.carrier_id})
        MERGE (s)-[r:SHIPPED_BY]->(c)
        SET r._source = $source,
            r._run_id = $run_id
        """,
        rows=rows,
        source=MANAGED_SOURCE,
        run_id=run_id,
    ).consume()


def merge_shipped_for(session: Session, rows: Sequence[dict[str, Any]], run_id: str) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MATCH (s:Shipment {shipment_id: row.shipment_id})
        MATCH (c:Customer {customer_id: row.customer_id})
        MERGE (s)-[r:SHIPPED_FOR]->(c)
        SET r._source = $source,
            r._run_id = $run_id
        """,
        rows=rows,
        source=MANAGED_SOURCE,
        run_id=run_id,
    ).consume()


def merge_uses_route(session: Session, rows: Sequence[dict[str, Any]], run_id: str) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MATCH (s:Shipment {shipment_id: row.shipment_id})
        MATCH (r:Route {route_id: row.route_id})
        MERGE (s)-[rel:USES_ROUTE]->(r)
        SET rel._source = $source,
            rel._run_id = $run_id
        """,
        rows=rows,
        source=MANAGED_SOURCE,
        run_id=run_id,
    ).consume()


def merge_has_event(session: Session, rows: Sequence[dict[str, Any]], run_id: str) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MATCH (s:Shipment {shipment_id: row.shipment_id})
        MATCH (e:ShipmentEvent {event_id: row.event_id})
        MERGE (s)-[r:HAS_EVENT]->(e)
        SET r._source = $source,
            r._run_id = $run_id
        """,
        rows=rows,
        source=MANAGED_SOURCE,
        run_id=run_id,
    ).consume()


def merge_has_exception(session: Session, rows: Sequence[dict[str, Any]], run_id: str) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MATCH (s:Shipment {shipment_id: row.shipment_id})
        MATCH (x:Exception {exception_id: row.exception_id})
        MERGE (s)-[r:HAS_EXCEPTION]->(x)
        SET r._source = $source,
            r._run_id = $run_id
        """,
        rows=rows,
        source=MANAGED_SOURCE,
        run_id=run_id,
    ).consume()


def delete_stale_relationships(session: Session, run_id: str) -> dict[str, int]:
    """Remove managed relationships not written by the current ingestion run.

    Only relationships tagged with the managed source are ever touched, and only
    those left over from a prior run (a different run id). Runs before node
    cleanup so a changed reference (e.g. a shipment moved to a different carrier)
    drops the old edge even though both endpoint nodes still exist.
    """
    removed: dict[str, int] = {}
    for relationship_type in MANAGED_RELATIONSHIP_TYPES:
        stale_count = session.run(
            f"""
            MATCH ()-[r:{relationship_type}]->()
            WHERE r._source = $source AND r._run_id <> $run_id
            RETURN count(r) AS stale_count
            """,
            source=MANAGED_SOURCE,
            run_id=run_id,
        ).single()["stale_count"]

        if stale_count:
            session.run(
                f"""
                MATCH ()-[r:{relationship_type}]->()
                WHERE r._source = $source AND r._run_id <> $run_id
                DELETE r
                """,
                source=MANAGED_SOURCE,
                run_id=run_id,
            ).consume()

        removed[relationship_type] = stale_count
    return removed


def delete_stale_nodes(session: Session, run_id: str) -> dict[str, int]:
    """Remove managed nodes not written by the current ingestion run.

    Only nodes tagged with the managed source are ever touched. Call after
    delete_stale_relationships so no managed relationship is left dangling
    from a node this removes.
    """
    removed: dict[str, int] = {}
    for label in MANAGED_NODE_LABELS:
        stale_count = session.run(
            f"""
            MATCH (n:{label})
            WHERE n._source = $source AND n._run_id <> $run_id
            RETURN count(n) AS stale_count
            """,
            source=MANAGED_SOURCE,
            run_id=run_id,
        ).single()["stale_count"]

        if stale_count:
            session.run(
                f"""
                MATCH (n:{label})
                WHERE n._source = $source AND n._run_id <> $run_id
                DETACH DELETE n
                """,
                source=MANAGED_SOURCE,
                run_id=run_id,
            ).consume()

        removed[label] = stale_count
    return removed


def count_nodes_by_label(session: Session) -> dict[str, int]:
    counts: dict[str, int] = {}
    for label in MANAGED_NODE_LABELS:
        record = session.run(f"MATCH (n:{label}) RETURN count(n) AS node_count").single()
        counts[label] = record["node_count"] if record else 0
    return counts


def count_relationships_by_type(session: Session) -> dict[str, int]:
    counts: dict[str, int] = {}
    for relationship_type in MANAGED_RELATIONSHIP_TYPES:
        record = session.run(
            f"MATCH ()-[r:{relationship_type}]->() RETURN count(r) AS relationship_count"
        ).single()
        counts[relationship_type] = record["relationship_count"] if record else 0
    return counts


def _strip_internal_properties(node: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in node.items() if not key.startswith("_")}


def get_shipment_context(session: Session, shipment_id: str) -> dict[str, Any] | None:
    """Return a shipment with its carrier, customer, route, ordered events, and exception."""
    record = session.run(
        """
        MATCH (s:Shipment {shipment_id: $shipment_id})
        OPTIONAL MATCH (s)-[:SHIPPED_BY]->(carrier:Carrier)
        OPTIONAL MATCH (s)-[:SHIPPED_FOR]->(customer:Customer)
        OPTIONAL MATCH (s)-[:USES_ROUTE]->(route:Route)
        OPTIONAL MATCH (s)-[:HAS_EXCEPTION]->(exception:Exception)
        OPTIONAL MATCH (s)-[:HAS_EVENT]->(event:ShipmentEvent)
        WITH s, carrier, customer, route, exception, event
        ORDER BY event.event_timestamp
        WITH s, carrier, customer, route, exception, collect(event) AS events
        RETURN s AS shipment, carrier, customer, route, exception, events
        """,
        shipment_id=shipment_id,
    ).single()

    if record is None or record["shipment"] is None:
        return None

    return {
        "shipment": _strip_internal_properties(dict(record["shipment"])),
        "carrier": _strip_internal_properties(dict(record["carrier"]))
        if record["carrier"] is not None
        else None,
        "customer": _strip_internal_properties(dict(record["customer"]))
        if record["customer"] is not None
        else None,
        "route": _strip_internal_properties(dict(record["route"]))
        if record["route"] is not None
        else None,
        "exception": _strip_internal_properties(dict(record["exception"]))
        if record["exception"] is not None
        else None,
        "events": [
            _strip_internal_properties(dict(event)) for event in record["events"] if event is not None
        ],
    }


def get_peer_shipments_by_carrier_and_route(
    session: Session, shipment_id: str, limit: int = 10
) -> list[dict[str, Any]]:
    """Return other shipments sharing the same carrier and route as shipment_id.

    Excludes the source shipment. Returns an empty list when the shipment does
    not exist or has no matching peers.
    """
    result = session.run(
        """
        MATCH (s:Shipment {shipment_id: $shipment_id})-[:SHIPPED_BY]->(carrier:Carrier)
        MATCH (s)-[:USES_ROUTE]->(route:Route)
        MATCH (peer:Shipment)-[:SHIPPED_BY]->(carrier)
        MATCH (peer)-[:USES_ROUTE]->(route)
        WHERE peer.shipment_id <> $shipment_id
        OPTIONAL MATCH (peer)-[:HAS_EXCEPTION]->(exception:Exception)
        RETURN peer.shipment_id AS shipment_id,
               peer.shipment_status AS shipment_status,
               peer.is_delayed AS is_delayed,
               peer.delay_days AS delay_days,
               peer.exception_flag AS exception_flag,
               exception.exception_type AS exception_type
        ORDER BY peer.is_delayed DESC, peer.delay_days DESC, peer.shipment_id
        LIMIT $limit
        """,
        shipment_id=shipment_id,
        limit=limit,
    )
    return result.data()


def get_exception_precedents(
    session: Session, shipment_id: str, limit: int = 10
) -> list[dict[str, Any]]:
    """Return other shipments with the same exception type on the same carrier or route.

    Excludes the source shipment. Returns an empty list when the shipment does
    not exist, has no exception, or has no matching precedent.
    """
    result = session.run(
        """
        MATCH (s:Shipment {shipment_id: $shipment_id})-[:HAS_EXCEPTION]->(current:Exception)
        MATCH (s)-[:SHIPPED_BY]->(carrier:Carrier)
        MATCH (s)-[:USES_ROUTE]->(route:Route)
        MATCH (precedent:Shipment)-[:HAS_EXCEPTION]->(pastException:Exception)
        WHERE pastException.exception_type = current.exception_type
          AND precedent.shipment_id <> $shipment_id
          AND (
            (precedent)-[:SHIPPED_BY]->(carrier)
            OR (precedent)-[:USES_ROUTE]->(route)
          )
        RETURN precedent.shipment_id AS shipment_id,
               pastException.exception_type AS exception_type,
               pastException.severity AS severity,
               pastException.resolution_status AS resolution_status,
               pastException.detected_at AS detected_at
        ORDER BY pastException.detected_at DESC
        LIMIT $limit
        """,
        shipment_id=shipment_id,
        limit=limit,
    )
    return result.data()
