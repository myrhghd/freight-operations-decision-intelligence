# Project Brief

## Business Context

Freight operations teams track shipments across many carriers, lanes, and
customers simultaneously. When a shipment is delayed or flagged with an
exception, the people responsible for resolving it need fast answers to
straightforward questions: where is this shipment, is it at risk, which
carriers or lanes are underperforming, and what is the standard procedure for
handling the disruption in front of them. Today those answers are spread
across shipment records, event logs, carrier performance data, and written
standard operating procedures (SOPs) that are not easy to search quickly.

## Intended Users

- Freight/logistics operations coordinators handling day-to-day shipment
  monitoring and exception response.
- Carrier and customer account managers reviewing performance and risk.
- Anyone evaluating this project as a demonstration of applied data and
  retrieval techniques in a logistics context.

## Primary Business Question

> How can shipment, event, carrier, route, exception, and operating-procedure
> data help logistics teams identify shipment status, explain disruptions, and
> determine appropriate next actions?

## Project Objective

Provide a local, self-contained tool that lets a user look up a shipment,
understand its status and history, see which shipments and lanes carry
elevated risk, and retrieve the relevant SOP guidance for handling a given
type of disruption — all from a single interface backed by a single API.

## Core Use Cases

1. Look up a specific shipment's status, route, and delivery dates.
2. Review the event timeline for a specific shipment.
3. Review delay-rate analytics broken down by carrier and lane.
4. Identify high-risk shipments (delayed, exception-flagged, or on
   historically high-delay lanes).
5. Ask a natural-language question and be routed to the right data view or to
   relevant SOP content.
6. Search SOP/FAQ documents directly for procedure guidance (e.g., customs
   delay escalation, weather delay policy).

## Business Value

- Reduces the time spent manually cross-referencing shipment data and SOP
  documents during an active disruption.
- Gives a consistent, queryable view of delay and risk patterns across
  carriers and lanes.
- Demonstrates a retrieval-based approach to SOP lookup that can be extended
  later without requiring a rebuild of the underlying data model.

## Data Entities

- **Carriers** — carrier identity, type, on-time rate, average transit days,
  risk score.
- **Customers** — customer identity, tier, industry, region.
- **Routes** — origin/destination, distance, lane type, historical delay
  rate.
- **Shipments** — status, mode, planned/actual dates, delay flag and days,
  exception flag, freight cost, and foreign keys to carrier/customer/route.
- **Shipment events** — timestamped status events per shipment (e.g.
  `CREATED`, `IN_TRANSIT`, `DELAYED`, `DELIVERED`).
- **Exceptions** — exception type, severity, detection time, resolution
  status, and recommended action, linked to a shipment.
- **SOP/FAQ documents** — markdown standard operating procedures covering
  carrier escalation, customer notification, customs delay escalation, and
  weather delay handling.

## Success Criteria

- A user can retrieve any generated shipment's status and event history.
- A user can retrieve delay and risk analytics across carriers and lanes.
- A user can ask an SOP-related question and receive the relevant SOP text
  and source document.
- The full workflow (data generation, database build, SOP ingestion, API,
  and UI) runs locally from a clean environment without external services
  beyond downloading the embedding model on first run.

## Scope

- Synthetic shipment, carrier, customer, route, event, and exception data.
- A FastAPI backend exposing shipment, analytics, and assistant endpoints.
- A DuckDB operational database built from the synthetic data.
- A Chroma vector store over a fixed set of sample SOP documents.
- A deterministic (non-generative) assistant router.
- A Streamlit UI covering shipment lookup, events, analytics, and the
  assistant.

## Out of Scope (current phase)

- Real or production freight data.
- Any generative language model (no text is generated; SOP answers are
  retrieved verbatim).
- GraphRAG or graph-database-backed retrieval (e.g., Neo4j).
- Authentication, multi-user access control, or deployment infrastructure.
- Containerized (Docker) reproducibility.

## Assumptions and Limitations

- All shipment, carrier, customer, and route data is synthetic and generated
  locally with a fixed random seed; it does not reflect real-world freight
  patterns beyond the rules encoded in the generator.
- Assistant routing is keyword- and pattern-based, not model-driven, and will
  misroute questions that fall outside its known phrasing patterns.
- SOP retrieval depends on the fixed set of sample documents in
  `data/sample_sops/`; it has no knowledge outside those documents.
- The system is designed for local, single-user use and has not been
  evaluated for concurrent or production use.
