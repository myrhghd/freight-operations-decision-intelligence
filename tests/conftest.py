from __future__ import annotations

from pathlib import Path

import pytest

import app.data.generate_synthetic_data as data_gen
import app.data.load_data as data_load


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
