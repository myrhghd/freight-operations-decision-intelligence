from __future__ import annotations

from typing import Any

from app.graph import queries
from app.graph.connection import get_session


GRAPH_UNAVAILABLE_ERROR = "Neo4j is currently unavailable."


def get_shipment_graph_context(shipment_id: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return the connected shipment context, or (None, error) if Neo4j cannot be reached.

    error is None whenever Neo4j was reached successfully, even if the shipment
    has no node in the graph yet (the first element is then also None).
    """
    try:
        with get_session() as session:
            context = queries.get_shipment_context(session, shipment_id)
        return context, None
    except Exception:
        return None, GRAPH_UNAVAILABLE_ERROR


def get_peer_shipments(
    shipment_id: str, limit: int = 10
) -> tuple[list[dict[str, Any]], str | None]:
    """Return peer shipments sharing the same carrier and route, or ([], error) if unavailable."""
    try:
        with get_session() as session:
            peers = queries.get_peer_shipments_by_carrier_and_route(session, shipment_id, limit)
        return peers, None
    except Exception:
        return [], GRAPH_UNAVAILABLE_ERROR


def get_exception_precedents(
    shipment_id: str, limit: int = 10
) -> tuple[list[dict[str, Any]], str | None]:
    """Return prior shipments with the same exception type, or ([], error) if unavailable."""
    try:
        with get_session() as session:
            precedents = queries.get_exception_precedents(session, shipment_id, limit)
        return precedents, None
    except Exception:
        return [], GRAPH_UNAVAILABLE_ERROR
