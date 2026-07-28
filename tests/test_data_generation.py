from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

EXPECTED_FILE_COLUMNS = {
    "carriers.csv": {"carrier_id", "carrier_name", "carrier_type", "on_time_rate"},
    "customers.csv": {"customer_id", "customer_name", "customer_tier"},
    "routes.csv": {"route_id", "origin_city", "destination_city", "distance_miles"},
    "shipments.csv": {"shipment_id", "customer_id", "carrier_id", "route_id", "is_delayed"},
    "shipment_events.csv": {"event_id", "shipment_id", "event_timestamp", "event_type"},
    "exceptions.csv": {"exception_id", "shipment_id", "exception_type"},
}


def test_synthetic_data_files_are_generated(synthetic_data_dir: Path) -> None:
    for filename in EXPECTED_FILE_COLUMNS:
        assert (synthetic_data_dir / filename).exists()


def test_synthetic_data_has_expected_columns_and_records(synthetic_data_dir: Path) -> None:
    for filename, expected_columns in EXPECTED_FILE_COLUMNS.items():
        dataframe = pd.read_csv(synthetic_data_dir / filename)
        assert expected_columns.issubset(dataframe.columns)
        assert len(dataframe) > 0

    shipments = pd.read_csv(synthetic_data_dir / "shipments.csv")
    assert len(shipments) == 1_000


def test_duckdb_tables_are_created_with_matching_row_counts(test_database_path: Path) -> None:
    with duckdb.connect(test_database_path.as_posix(), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        assert {
            "carriers",
            "customers",
            "routes",
            "shipments",
            "shipment_events",
            "exceptions",
        }.issubset(tables)

        total_shipments = connection.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]
        assert total_shipments == 1_000
