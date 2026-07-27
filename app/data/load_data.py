from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "processed"
DB_PATH = DATA_DIR / "logistics.duckdb"


TABLE_TO_FILE = {
    "carriers": "carriers.csv",
    "customers": "customers.csv",
    "routes": "routes.csv",
    "shipments": "shipments.csv",
    "shipment_events": "shipment_events.csv",
    "exceptions": "exceptions.csv",
}


def load_table(connection: duckdb.DuckDBPyConnection, table_name: str, csv_path: Path) -> int:
    connection.execute(
        f"""
        CREATE OR REPLACE TABLE {table_name} AS
        SELECT *
        FROM read_csv_auto('{csv_path.as_posix()}', HEADER=TRUE)
        """
    )
    return connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(DB_PATH.as_posix()) as connection:
        print(f"Loading CSVs into: {DB_PATH}")

        loaded_counts: dict[str, int] = {}
        for table_name, filename in TABLE_TO_FILE.items():
            csv_path = DATA_DIR / filename
            if not csv_path.exists():
                raise FileNotFoundError(f"Missing CSV file: {csv_path}")
            loaded_counts[table_name] = load_table(connection, table_name, csv_path)

        print("\nLoaded table row counts:")
        for table_name in TABLE_TO_FILE:
            print(f"- {table_name}: {loaded_counts[table_name]:,}")

        total_shipments = connection.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]
        delayed_shipments = connection.execute(
            "SELECT COUNT(*) FROM shipments WHERE is_delayed = TRUE"
        ).fetchone()[0]
        exception_records = connection.execute("SELECT COUNT(*) FROM exceptions").fetchone()[0]
        flagged_shipments = connection.execute(
            "SELECT COUNT(*) FROM shipments WHERE exception_flag = TRUE"
        ).fetchone()[0]

        unmatched_exceptions = connection.execute(
            """
            SELECT COUNT(*)
            FROM exceptions e
            LEFT JOIN shipments s ON s.shipment_id = e.shipment_id
            WHERE s.exception_flag IS DISTINCT FROM TRUE
            """
        ).fetchone()[0]

        print("\nValidation:")
        print(f"- total_shipments: {total_shipments:,}")
        print(f"- delayed_shipments: {delayed_shipments:,}")
        print(f"- exception_records: {exception_records:,}")
        print(f"- exception_flag_shipments: {flagged_shipments:,}")
        print(
            "- exception records match exception_flag shipments: "
            f"{'PASS' if exception_records == flagged_shipments and unmatched_exceptions == 0 else 'FAIL'}"
        )


if __name__ == "__main__":
    main()
