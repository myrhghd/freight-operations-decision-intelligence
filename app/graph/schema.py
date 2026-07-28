from __future__ import annotations

from neo4j import Session


CONSTRAINTS = [
    "CREATE CONSTRAINT shipment_id_unique IF NOT EXISTS "
    "FOR (s:Shipment) REQUIRE s.shipment_id IS UNIQUE",
    "CREATE CONSTRAINT carrier_id_unique IF NOT EXISTS "
    "FOR (c:Carrier) REQUIRE c.carrier_id IS UNIQUE",
    "CREATE CONSTRAINT customer_id_unique IF NOT EXISTS "
    "FOR (c:Customer) REQUIRE c.customer_id IS UNIQUE",
    "CREATE CONSTRAINT route_id_unique IF NOT EXISTS "
    "FOR (r:Route) REQUIRE r.route_id IS UNIQUE",
    "CREATE CONSTRAINT shipment_event_id_unique IF NOT EXISTS "
    "FOR (e:ShipmentEvent) REQUIRE e.event_id IS UNIQUE",
    "CREATE CONSTRAINT exception_id_unique IF NOT EXISTS "
    "FOR (x:Exception) REQUIRE x.exception_id IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX shipment_is_delayed IF NOT EXISTS FOR (s:Shipment) ON (s.is_delayed)",
    "CREATE INDEX shipment_exception_flag IF NOT EXISTS FOR (s:Shipment) ON (s.exception_flag)",
    "CREATE INDEX route_historical_delay_rate IF NOT EXISTS "
    "FOR (r:Route) ON (r.historical_delay_rate)",
    "CREATE INDEX exception_type_lookup IF NOT EXISTS FOR (x:Exception) ON (x.exception_type)",
    "CREATE INDEX shipment_event_timestamp IF NOT EXISTS "
    "FOR (e:ShipmentEvent) ON (e.event_timestamp)",
    "CREATE INDEX carrier_risk_score IF NOT EXISTS FOR (c:Carrier) ON (c.risk_score)",
]


def apply_schema(session: Session) -> None:
    """Create the graph constraints and indexes. Safe to run repeatedly."""
    for statement in CONSTRAINTS:
        session.run(statement).consume()
    for statement in INDEXES:
        session.run(statement).consume()
