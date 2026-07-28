from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import app.data.generate_synthetic_data as data_gen
import app.data.load_data as data_load
import app.db.connection as db_connection
import app.graph.connection as graph_connection
from app.graph.connection import close_driver, graph_health_check
from app.graph.load_graph import run_ingestion


# Isolated Neo4j instance for tests only, started with:
#   docker compose --profile test up -d neo4j-test
# Kept separate from the bolt://localhost:7687 development service so graph
# tests can never modify development graph data.
GRAPH_TEST_URI = "bolt://localhost:17687"


@pytest.fixture(scope="session")
def synthetic_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate one synthetic dataset for the whole test session, isolated from data/processed."""
    output_dir = tmp_path_factory.mktemp("synthetic_data")
    original_output_dir = data_gen.OUTPUT_DIR
    data_gen.OUTPUT_DIR = output_dir
    try:
        data_gen.main()
    finally:
        data_gen.OUTPUT_DIR = original_output_dir
    return output_dir


@pytest.fixture(scope="session")
def test_database_path(
    synthetic_data_dir: Path, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """Load the session synthetic dataset into an isolated DuckDB file."""
    db_path = tmp_path_factory.mktemp("db") / "logistics.duckdb"
    original_data_dir = data_load.DATA_DIR
    original_db_path = data_load.DB_PATH
    data_load.DATA_DIR = synthetic_data_dir
    data_load.DB_PATH = db_path
    try:
        data_load.main()
    finally:
        data_load.DATA_DIR = original_data_dir
        data_load.DB_PATH = original_db_path
    return db_path


@pytest.fixture
def use_test_database(
    test_database_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Point app.db.connection at the isolated test database for the duration of a test."""
    monkeypatch.setattr("app.db.connection.DATABASE_PATH", test_database_path)


@pytest.fixture(scope="session")
def use_test_graph() -> Iterator[None]:
    """Point app.graph.connection at the isolated neo4j-test service for the session.

    Any driver already created against the development URI is closed first, so
    the next get_driver() call is guaranteed to connect to the test service
    instead. The development URI is restored on teardown for the same reason.
    """
    graph_connection.close_driver()
    original_uri = graph_connection.NEO4J_URI
    graph_connection.NEO4J_URI = GRAPH_TEST_URI
    try:
        yield
    finally:
        graph_connection.close_driver()
        graph_connection.NEO4J_URI = original_uri


@pytest.fixture(scope="session")
def require_neo4j(use_test_graph: None) -> None:
    """Skip dependent tests clearly when the isolated Neo4j test service is unreachable."""
    if not graph_health_check():
        pytest.skip(
            f"Neo4j test service is not reachable at {GRAPH_TEST_URI}; skipping graph tests."
        )


@pytest.fixture(scope="session", autouse=True)
def _close_graph_driver_at_session_end() -> Iterator[None]:
    yield
    close_driver()


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
