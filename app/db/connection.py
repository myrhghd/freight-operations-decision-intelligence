from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import duckdb

from app.core.config import DATABASE_PATH


def get_connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(DATABASE_PATH.as_posix(), read_only=True)


def fetch_one(query: str, params: Sequence[Any] | None = None) -> dict[str, Any] | None:
    with get_connection() as connection:
        cursor = connection.execute(query, params or [])
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))


def fetch_all(query: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
    with get_connection() as connection:
        cursor = connection.execute(query, params or [])
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in rows]
