from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from neo4j import Driver, GraphDatabase, Session

from app.core.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER


_driver: Driver | None = None


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD),
            connection_timeout=5.0,
        )
    return _driver


@contextmanager
def get_session() -> Iterator[Session]:
    session = get_driver().session()
    try:
        yield session
    finally:
        session.close()


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def graph_health_check() -> bool:
    try:
        with get_session() as session:
            session.run("RETURN 1").consume()
        return True
    except Exception:
        return False
