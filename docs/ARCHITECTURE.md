# Architecture

This document describes the current system as verified in this repository.

## Components

### FastAPI backend (`app/api`)

Exposes the HTTP API consumed by the Streamlit interface:

- `GET /health`
- `GET /health/graph`
- `GET /shipments/{shipment_id}`
- `GET /shipments/{shipment_id}/events`
- `GET /analytics/delay-rates`
- `GET /analytics/high-risk-shipments`
- `POST /assistant/sop-search`
- `POST /assistant/chat`

`/health` reports on the FastAPI service only and does not depend on
Neo4j. `/health/graph` reports the Neo4j connection status separately,
returning a 503 status when the graph service is unreachable, so the API
starts and serves shipment, analytics, and SOP requests normally even when
Neo4j is not running.

Routing is split into `app/api/routes/shipments.py`,
`app/api/routes/analytics.py`, and `app/api/routes/assistant.py`, each
delegating to a service module.

### Streamlit interface (`app/ui/streamlit_app.py`)

An interface with several pages (Home, Shipment Lookup, Shipment Events,
Delay Analytics, High Risk Shipments, SOP Assistant, Assistant Chat) that
calls the local FastAPI backend over HTTP using the `requests` library. It
performs no data access or business logic of its own; all data comes from
the API.

### DuckDB operational database (`app/db`, `data/processed/logistics.duckdb`)

`app/db/connection.py` opens read only DuckDB connections and exposes
`fetch_one` and `fetch_all` helpers used by the service layer. The database
is a local file built from the synthetic CSVs. It is not committed to
version control and is rebuilt using the loader script.

### Synthetic data generator and loader (`app/data`)

- `generate_synthetic_data.py` produces carriers, customers, routes,
  shipments, shipment events, and exceptions as CSV files under
  `data/processed/`, using NumPy and Pandas with a fixed random seed for
  reproducibility.
- `load_data.py` loads those CSVs into the DuckDB database and runs row
  count and referential consistency checks, confirming for example that
  every flagged shipment has a matching exception record.

### Chroma vector store and Sentence Transformer embeddings (`app/rag`)

- `ingest_docs.py` reads the markdown SOP documents in
  `data/sample_sops/`, splits them into section and paragraph sized chunks,
  and embeds each chunk with the `sentence-transformers/all-MiniLM-L6-v2`
  model. Embeddings and chunk text are stored in a local, persistent Chroma
  collection under `data/processed/chroma/`.
- `retriever.py` embeds an incoming question with the same model, queries
  the Chroma collection for the closest matching chunks, and returns them
  with their source document and distance score. It then builds an answer
  by joining the retrieved chunk text directly, without generating new text.

### Deterministic assistant routing (`app/services/assistant_service.py`)

Given a natural language question, `route_question` uses a shipment ID
pattern and keyword matching to classify the question into one of: shipment
lookup, shipment events, delay analytics, high risk shipments, or SOP
search. `build_chat_response` then calls the corresponding service function
and returns its result along with the chosen route. Routing is rule based
and produces the same result for the same input every time.

### Shipment lookup and analytics services (`app/services/shipment_service.py`)

Contains the SQL queries and thin wrapper functions used by both the API
routes and the assistant:

- `get_shipment_details` and `get_shipment_events` for single shipment
  lookups.
- `get_delay_rates` for delay rate and average delay days grouped by
  carrier and lane.
- `get_high_risk_shipments` for shipments that are delayed, flagged with an
  exception, or on a route with a historically elevated delay rate.

### Neo4j graph store (`app/graph`, local Neo4j Community Edition)

A local Neo4j Community Edition instance, started with `docker compose up -d
neo4j`, holds a graph representation of the same shipment, carrier,
customer, route, event, and exception data already stored in DuckDB. Neo4j
does not replace DuckDB or Chroma; it complements them by making
relationship traversal across these entities direct instead of requiring
several SQL joins.

- `connection.py` creates the Neo4j driver from the connection settings in
  `app/core/config.py`, provides a session context manager, closes the
  driver on shutdown, and exposes a `graph_health_check` function used by
  `/health/graph`.
- `schema.py` defines uniqueness constraints and indexes for each node type
  and applies them through statements that use `IF NOT EXISTS`, so running
  schema setup again has no effect beyond the first run.
- `queries.py` contains the parameterized, batched Cypher statements used
  for ingestion, node and relationship count helpers, and the connected
  shipment context query.
- `load_graph.py` reads the current DuckDB tables directly (through
  `app/db/connection.py`), validates that every foreign key in the tables
  resolves, applies the schema, and ingests carriers, customers, routes,
  shipments, shipment events, and exceptions using `MERGE` statements keyed
  on each entity's unique id. It runs as `python -m app.graph.load_graph`.

Graph nodes hold only the properties needed for identification, filtering,
and explanation, not every column from the corresponding DuckDB table.

### Graph synchronization

DuckDB is the source of truth. Every node and relationship written by
`load_graph.py` is tagged with an internal `_source` property (always
`duckdb`) and an `_run_id` property set to a fresh identifier generated at
the start of that ingestion run. After the current DuckDB rows have been
merged, ingestion removes any managed relationship, then any managed node,
still carrying an older `_run_id`. This reconciles the graph to match
DuckDB exactly on every run:

- A row deleted from DuckDB (for example an exception that no longer
  exists) is removed from Neo4j on the next ingestion, instead of being
  left behind indefinitely.
- A changed foreign key (for example a shipment reassigned to a different
  carrier) drops the old relationship and keeps only the new one, even
  though both endpoint nodes still exist.
- Only nodes and relationships tagged `_source: duckdb` are ever
  considered for removal, so anything created outside the ingestion
  pipeline is left untouched.
- Cleanup runs only after every merge in that run has succeeded, so a
  failed ingestion never deletes graph data that was correct before it
  started.
- Running ingestion again with unchanged DuckDB data removes nothing; node
  and relationship counts stay the same.

`_source` and `_run_id` are internal bookkeeping fields. `get_shipment_context`
strips them before returning a node.

Node types: `Shipment`, `Carrier`, `Customer`, `Route`, `ShipmentEvent`,
`Exception`.

Relationships, each directed from the shipment outward:

```
(Shipment)-[:SHIPPED_BY]->(Carrier)
(Shipment)-[:SHIPPED_FOR]->(Customer)
(Shipment)-[:USES_ROUTE]->(Route)
(Shipment)-[:HAS_EVENT]->(ShipmentEvent)
(Shipment)-[:HAS_EXCEPTION]->(Exception)
```

No SOP nodes or inferred relationships exist in the graph. SOP retrieval
remains entirely inside Chroma, and the assistant router has not been
connected to the graph.

### Isolated Neo4j test service

`docker-compose.yml` also defines `neo4j-test`, a second Neo4j Community
Edition service behind the `test` Compose profile, so a plain
`docker compose up` never starts it. It listens on `bolt://localhost:17687`
and `http://localhost:17474` (the development service keeps
`bolt://localhost:7687` and `http://localhost:7474`), has no named volume,
and reuses the same local credentials as the development service. Start it
with:

```bash
docker compose --profile test up -d neo4j-test
```

Stop and remove it, discarding its data, with:

```bash
docker compose stop neo4j-test
docker compose rm -f neo4j-test
```

Graph integration tests in `tests/test_graph.py` point `app.graph.connection`
at this service for the whole test session and restore the development URI
on teardown, so running the test suite never reads or writes the
development graph. Because Neo4j Community Edition supports only one user
database per instance, a separate service, rather than a separate database
on the same instance, is what keeps test data apart from development data.
Tests skip clearly, with a message naming the unreachable URL, when
`neo4j-test` is not running.

### Local environment configuration (`app/core/config.py`)

Connection settings for Neo4j come from environment variables, loaded with
`python-dotenv`'s `load_dotenv`. Values already present in the process
environment take priority over `.env`, and a missing `.env` file does not
raise; the driver itself is never created at import time, only on first
use.

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=change_this_password
```

`.env` is listed in `.gitignore` and is never committed. `.env.example`
documents the expected keys with placeholder values only.

### SOP retrieval flow

1. A question arrives through `/assistant/sop-search` or is routed to SOP
   search by `/assistant/chat`.
2. `retrieve_sop_chunks` embeds the question and queries Chroma for the
   closest matching chunks (three by default).
3. `extractive_answer_from_chunks` joins the retrieved chunk text and
   collects the distinct source document names.
4. The response includes the combined text, the list of source documents,
   and the individual chunks (text, source, chunk index, distance).

## Current Data Flow

```
generate_synthetic_data.py --> CSV files (data/processed/*.csv)
                                       |
                                       v
                              load_data.py --> logistics.duckdb
                                       |
                                       v
                         FastAPI (app/api) <-- app/services (SQL queries)
                                       |
                                       v
                         Streamlit interface (app/ui) [HTTP calls]

data/sample_sops/*.md --> ingest_docs.py --> Chroma collection
                                                  |
                                                  v
                                       retriever.py <-- FastAPI /assistant routes

logistics.duckdb --> load_graph.py --> Neo4j (local, docker compose)
                                                  |
                                                  v
                                       app/graph/connection.py <-- /health/graph
```

## Repository Structure

```
app/
├── api/
│   ├── main.py                 FastAPI app, /health, and /health/graph endpoints
│   └── routes/                 shipments, analytics, assistant routers
├── core/
│   └── config.py                project paths, service name, and Neo4j settings
├── data/
│   ├── generate_synthetic_data.py
│   └── load_data.py
├── db/
│   └── connection.py            DuckDB read only connection helpers
├── graph/
│   ├── connection.py             Neo4j driver, session, cleanup, health check
│   ├── schema.py                 idempotent constraints and indexes
│   ├── queries.py                batched Cypher for ingestion, sync cleanup, and the connected shipment query
│   └── load_graph.py             synchronized ingestion from DuckDB into Neo4j
├── rag/
│   ├── ingest_docs.py           SOP chunking, embedding, Chroma ingestion
│   └── retriever.py             embedding based retrieval and extractive answer
├── services/
│   ├── assistant_service.py     deterministic question routing
│   └── shipment_service.py      shipment and analytics SQL queries
└── ui/
    └── streamlit_app.py          Streamlit interface

data/
├── processed/                   generated CSVs, DuckDB file, Chroma store (not committed)
├── raw/                         not currently used
└── sample_sops/                 sample SOP and FAQ markdown documents

tests/
├── test_graph.py                  graph schema, ingestion, sync, and query tests (isolated Neo4j service)
├── test_config.py                 .env loading behavior
└── ...                             data generation, service, routing, and API tests

docs/                             project documentation
requirements.txt                  pinned Python dependencies
docker-compose.yml                defines the local and test Neo4j Community Edition services
```

## Validation Commands

`docker compose config` prints the fully resolved configuration, including
the interpolated `NEO4J_AUTH` value with the local password in plain text.
Use the quiet form to validate the file without printing anything:

```bash
docker compose config --quiet
```
