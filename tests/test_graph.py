from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

import app.db.connection as db_connection
from app.graph import queries
from app.graph.connection import get_session
from app.graph.load_graph import run_ingestion
from app.graph.schema import apply_schema

# require_neo4j pulls in use_test_graph, so every test in this module runs
# against bolt://localhost:17687 (neo4j-test), never the development service
# on bolt://localhost:7687. The synchronization tests near the end of this
# file mutate the isolated test dataset and rely on running after the count
# and query assertions above them; keep new tests in that relative order.
pytestmark = pytest.mark.usefixtures("require_neo4j")

EXISTING_SHIPMENT_ID = "SHP-1001"
MISSING_SHIPMENT_ID = "SHP-9999"
UNMANAGED_CARRIER_ID = "CAR-UNMANAGED-TEST"

EXPECTED_SOURCE_COUNTS = {
    "carriers": 10,
    "customers": 50,
    "routes": 25,
    "shipments": 1_000,
    "shipment_events": 5_000,
    "exceptions": 180,
}

EXPECTED_NODE_COUNTS = {
    "Shipment": 1_000,
    "Carrier": 10,
    "Customer": 50,
    "Route": 25,
    "ShipmentEvent": 5_000,
    "Exception": 180,
}

EXPECTED_RELATIONSHIP_COUNTS = {
    "SHIPPED_BY": 1_000,
    "SHIPPED_FOR": 1_000,
    "USES_ROUTE": 1_000,
    "HAS_EVENT": 5_000,
    "HAS_EXCEPTION": 180,
}


@pytest.fixture(scope="module")
def use_test_database_module(test_database_path: Path) -> Iterator[None]:
    """Point app.db.connection at the isolated synthetic dataset for the whole module.

    A module scoped fixture cannot depend on the function scoped monkeypatch
    fixture used elsewhere, so the swap is done manually here instead.
    """
    original_path = db_connection.DATABASE_PATH
    db_connection.DATABASE_PATH = test_database_path
    try:
        yield
    finally:
        db_connection.DATABASE_PATH = original_path


@pytest.fixture(scope="module")
def ingested_graph(use_test_database_module: None) -> dict[str, int]:
    """Ingest the isolated synthetic dataset into the test graph once for the module."""
    return run_ingestion()


def test_schema_creation_succeeds() -> None:
    with get_session() as session:
        apply_schema(session)


def test_schema_creation_is_repeatable() -> None:
    with get_session() as session:
        apply_schema(session)
        apply_schema(session)


def test_ingestion_matches_source_row_counts(ingested_graph: dict[str, int]) -> None:
    for key, expected_count in EXPECTED_SOURCE_COUNTS.items():
        assert ingested_graph[key] == expected_count


def test_node_counts_match_expected(ingested_graph: dict[str, int]) -> None:
    with get_session() as session:
        node_counts = queries.count_nodes_by_label(session)
    assert node_counts == EXPECTED_NODE_COUNTS


def test_relationship_counts_match_expected(ingested_graph: dict[str, int]) -> None:
    with get_session() as session:
        relationship_counts = queries.count_relationships_by_type(session)
    assert relationship_counts == EXPECTED_RELATIONSHIP_COUNTS


def test_connected_shipment_query_returns_full_context(ingested_graph: dict[str, int]) -> None:
    with get_session() as session:
        context = queries.get_shipment_context(session, EXISTING_SHIPMENT_ID)

    assert context is not None
    assert context["shipment"]["shipment_id"] == EXISTING_SHIPMENT_ID
    assert context["carrier"] is not None
    assert context["customer"] is not None
    assert context["route"] is not None
    assert len(context["events"]) > 0

    timestamps = [event["event_timestamp"] for event in context["events"]]
    assert timestamps == sorted(timestamps)


def test_connected_shipment_query_missing_shipment_returns_none(
    ingested_graph: dict[str, int],
) -> None:
    with get_session() as session:
        context = queries.get_shipment_context(session, MISSING_SHIPMENT_ID)
    assert context is None


def test_repeated_ingestion_preserves_counts_when_data_is_unchanged(
    ingested_graph: dict[str, int],
) -> None:
    with get_session() as session:
        before_nodes = queries.count_nodes_by_label(session)
        before_relationships = queries.count_relationships_by_type(session)

    second_run_counts = run_ingestion()

    with get_session() as session:
        after_nodes = queries.count_nodes_by_label(session)
        after_relationships = queries.count_relationships_by_type(session)

    assert second_run_counts["removed_nodes"] == 0
    assert second_run_counts["removed_relationships"] == 0
    assert after_nodes == before_nodes
    assert after_relationships == before_relationships


def test_synchronization_removes_row_deleted_from_source(
    ingested_graph: dict[str, int], test_database_path: Path
) -> None:
    """A source row removed from DuckDB is removed from Neo4j on the next ingestion."""
    with duckdb.connect(test_database_path.as_posix(), read_only=False) as connection:
        removed_exception_id = connection.execute(
            "SELECT exception_id FROM exceptions LIMIT 1"
        ).fetchone()[0]
        connection.execute("DELETE FROM exceptions WHERE exception_id = ?", [removed_exception_id])

    counts = run_ingestion()

    assert counts["removed_nodes"] >= 1
    assert counts["removed_relationships"] >= 1

    with get_session() as session:
        remaining = session.run(
            "MATCH (x:Exception {exception_id: $exception_id}) RETURN x",
            exception_id=removed_exception_id,
        ).single()
        node_counts = queries.count_nodes_by_label(session)
        relationship_counts = queries.count_relationships_by_type(session)

    assert remaining is None
    assert node_counts["Exception"] == EXPECTED_NODE_COUNTS["Exception"] - 1
    assert relationship_counts["HAS_EXCEPTION"] == EXPECTED_RELATIONSHIP_COUNTS["HAS_EXCEPTION"] - 1


def test_synchronization_replaces_changed_relationship(test_database_path: Path) -> None:
    """A shipment moved to a different carrier drops the old edge and gains the new one."""
    with duckdb.connect(test_database_path.as_posix(), read_only=False) as connection:
        current_carrier_id = connection.execute(
            "SELECT carrier_id FROM shipments WHERE shipment_id = ?",
            [EXISTING_SHIPMENT_ID],
        ).fetchone()[0]
        new_carrier_id = "CAR-001" if current_carrier_id != "CAR-001" else "CAR-002"
        connection.execute(
            "UPDATE shipments SET carrier_id = ? WHERE shipment_id = ?",
            [new_carrier_id, EXISTING_SHIPMENT_ID],
        )

    run_ingestion()

    with get_session() as session:
        record = session.run(
            """
            MATCH (s:Shipment {shipment_id: $shipment_id})-[:SHIPPED_BY]->(c:Carrier)
            RETURN collect(c.carrier_id) AS carrier_ids
            """,
            shipment_id=EXISTING_SHIPMENT_ID,
        ).single()

    assert record["carrier_ids"] == [new_carrier_id]


def test_synchronization_does_not_delete_unmanaged_records() -> None:
    """Nodes without the managed source tag survive synchronization untouched."""
    with get_session() as session:
        session.run(
            "CREATE (:Carrier {carrier_id: $carrier_id, carrier_name: $carrier_name})",
            carrier_id=UNMANAGED_CARRIER_ID,
            carrier_name="Manually created, not owned by ingestion",
        ).consume()

    try:
        run_ingestion()

        with get_session() as session:
            record = session.run(
                "MATCH (c:Carrier {carrier_id: $carrier_id}) RETURN c",
                carrier_id=UNMANAGED_CARRIER_ID,
            ).single()

        assert record is not None
    finally:
        with get_session() as session:
            session.run(
                "MATCH (c:Carrier {carrier_id: $carrier_id}) DETACH DELETE c",
                carrier_id=UNMANAGED_CARRIER_ID,
            ).consume()
