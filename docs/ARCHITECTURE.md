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
calls the FastAPI backend over HTTP using the `requests` library. It
performs no data access or business logic of its own; all data comes from
the API. The backend base URL comes from the `API_BASE_URL` environment
variable, defaulting to `http://127.0.0.1:8000` for local Python use; the
`ui` container overrides it to `http://api:8000`, the API's service name on
the Compose network.

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
  with their source document and distance score. It then builds a
  deterministic fallback answer by joining the retrieved chunk text
  directly.

### Optional local SOP synthesis (`app/services/local_llm_service.py`)

When `LOCAL_LLM_ENABLED=true`, SOP search responses can be enhanced by a
local Ollama model after Chroma retrieval succeeds. The configured model is
`qwen2.5:1.5b`, accessed through the pinned Python package
`ollama==0.6.2`. The LLM receives only the user question and the retrieved
SOP evidence selected by the deterministic retriever. It never queries
DuckDB, Chroma, or Neo4j directly.

The LLM must return JSON with:

```json
{
  "answer": "...",
  "cited_evidence_ids": ["e1"]
}
```

`SOPGenerationResult` validates the response shape, rejects empty answers,
rejects empty or duplicate citations, rejects extra fields, and rejects
citations that do not match supplied evidence IDs. If the model is
disabled, unavailable, times out, returns malformed JSON, omits citations,
or fails validation, `assistant_service.py` returns the deterministic
extractive SOP answer unchanged.

This optional LLM path is deliberately narrow. It is not used for
assistant routing, SQL generation, Cypher generation, shipment lookup,
analytics, graph retrieval, tool calling, Streamlit logic, or autonomous
actions. Deterministic retrieval and business logic remain the source of
truth.

### Deterministic assistant routing (`app/services/assistant_service.py`)

Given a natural language question, `route_question` uses a shipment ID
pattern and keyword matching to classify the question into one of nine
routes: shipment lookup, shipment events, delay analytics, high risk
shipments, one of four graph routes described below, or SOP search.
`build_chat_response` then calls the corresponding service function and
returns its result along with the chosen route. Routing is rule based and
produces the same result for the same input every time. New keyword lists
are checked after the existing shipment lookup and shipment events terms
and before delay analytics and high risk terms, so no existing question
phrasing changes route.

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
  for ingestion, node and relationship count helpers, the connected
  shipment context query, a peer shipment query (other shipments sharing
  the same carrier and route), and an exception precedent query (other
  shipments with the same exception type on the same carrier or route).
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
remains entirely inside Chroma; the assistant router uses the graph for
relationship context and, for one route, passes a confirmed exception type
into the existing Chroma retriever, described in the next section.

### Hybrid retrieval routes (`app/services/graph_service.py`, `app/services/assistant_service.py`)

`app/services/graph_service.py` wraps the three Neo4j read operations the
assistant uses: `get_shipment_graph_context`, `get_peer_shipments`, and
`get_exception_precedents`. Each function returns a `(result, error)` pair
rather than raising: `error` is `None` whenever Neo4j was reached
successfully, even when the result is empty; `error` is a fixed message
when the connection or query fails, so a route can degrade instead of
returning an HTTP 500.

`assistant_service.py` adds four routes on top of the five described
above, all requiring a shipment ID in the question:

- `graph_shipment_explanation` — DuckDB confirms the shipment, then Neo4j's
  connected shipment context supplies its carrier, customer, route,
  ordered events, and exception for the answer.
- `graph_peer_shipments` — DuckDB confirms the shipment, then Neo4j returns
  other shipments sharing the same carrier and route.
- `graph_exception_precedents` — DuckDB confirms the shipment and checks
  its exception flag; only when an exception is present does Neo4j look up
  prior shipments with the same exception type on the same carrier or
  route.
- `graph_sop_explanation` — DuckDB confirms the shipment, Neo4j confirms
  its exception type; only when an exception is present is that type
  passed as the question to the existing, unchanged `retrieve_sop_chunks`
  and `extractive_answer_from_chunks` Chroma pipeline.

Every graph route checks DuckDB first; Neo4j and Chroma are never called
for a shipment ID that does not exist. All four share one response shape:

```json
{
  "question": "...",
  "route": "...",
  "answer": "...",
  "data": {
    "shipment": {},
    "graph_context": {},
    "peers": [],
    "precedents": [],
    "sop_guidance": null
  },
  "sources": [],
  "retrieval_sources": []
}
```

`retrieval_sources` lists only the backends that were actually reached for
that response (`duckdb`, `neo4j`, `chroma`), so a degraded answer is
identifiable from the response itself rather than only from its text.
Fields in `data` that a given route does not use keep their default value
(`null` for `graph_context`/`sop_guidance`, an empty list for
`peers`/`precedents`). The five original routes keep their original flat
`data` shape and do not include `retrieval_sources`; nothing about their
behavior or response changed.

When a graph or Chroma call fails, the affected route still returns a 200
response: the answer explains what is unavailable, the corresponding
`data` field stays at its default, and that backend is left out of
`retrieval_sources`. An unsupported question, and a question with keywords
but no shipment ID, both fall through to the existing `sop_search` branch
exactly as before.

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

### Application containers (`Dockerfile`, `docker-compose.yml`)

A single `Dockerfile` (Python 3.11, a nonroot `appuser`) builds one image,
`freight-visibility-app`, used by both the `api` and `ui` services; only
the Compose `command` differs between them. Local generated data, `.env`,
caches, and Git files are excluded through `.dockerignore`, so the image
only ever contains the application code and the sample SOP documents.

`docker-compose.yml` defines, in addition to `neo4j` and `neo4j-test`:

- `init` — runs once: generates synthetic data, builds the DuckDB
  database, ingests the SOP documents into Chroma, and loads the Neo4j
  graph, in that order. It waits for `neo4j`'s healthcheck before starting.
  `api` waits for `init` to exit successfully before it starts, so the API
  never starts against a missing database.
- `api` — the FastAPI service, with `NEO4J_URI` set to `bolt://neo4j:7687`
  (the service name on the Compose network, not `localhost`). Its
  healthcheck polls its own `/health` endpoint. Neo4j is only needed for
  `init`'s graph loading step and for `/health/graph`; the API container
  itself does not depend on `neo4j` directly and starts normally if Neo4j
  is ever unavailable at runtime, consistent with the graceful degradation
  described above.
- `ui` — the Streamlit interface, with `API_BASE_URL` set to `http://api:8000`
  so it reaches the API by service name rather than `localhost`. It waits
  for `api`'s healthcheck before starting. Its own healthcheck polls
  Streamlit's `/_stcore/health` endpoint.

Two named volumes support this: `app_data` (mounted at
`/app/data/processed` in `init` and `api`) persists the generated CSVs,
DuckDB file, and Chroma store across restarts; `hf_cache` (mounted at the
appuser's Hugging Face cache directory in the same two services) persists
the downloaded embedding model so it does not need to download again on
every restart. `neo4j_data` is unchanged from before. `.env` is never copied
into the image or exposed by any command; `docker compose config --quiet`
remains the way to validate the file without printing the interpolated
password.

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
LOCAL_LLM_ENABLED=false
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:1.5b
OLLAMA_KEEP_ALIVE=2m
OLLAMA_REQUEST_TIMEOUT_SECONDS=120
```

`.env` is listed in `.gitignore` and is never committed. `.env.example`
documents the expected keys with placeholder values only. Ollama must be
running separately when local LLM mode is enabled:

```bash
ollama pull qwen2.5:1.5b
ollama serve
```

### SOP retrieval flow

1. A question arrives through `/assistant/sop-search` or is routed to SOP
   search by `/assistant/chat`.
2. `retrieve_sop_chunks` embeds the question and queries Chroma for the
   closest matching chunks (three by default).
3. `extractive_answer_from_chunks` joins the retrieved chunk text and
   collects the distinct source document names. This is the deterministic
   fallback answer.
4. If local LLM mode is disabled, unavailable, or validation fails, the
   deterministic answer is returned unchanged.
5. If local LLM mode is enabled and retrieval produced valid SOP evidence,
   Ollama synthesizes a concise answer from that evidence only. The answer
   is accepted only when Pydantic validation and citation ID checks pass.
6. The response keeps the same public keys: `question`, `route`, `answer`,
   `data`, and `sources`.

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
                                                  |
                                                  v
                         optional Ollama SOP synthesis (validated JSON + citations)

logistics.duckdb --> load_graph.py --> Neo4j (local, docker compose)
                                                  |
                                                  v
                                       app/graph/connection.py <-- /health/graph

FastAPI /assistant/chat --> assistant_service.build_chat_response
        |                              |                    |
        v                              v                    v
  shipment_service (DuckDB)   graph_service (Neo4j)   retriever (Chroma, graph_sop_explanation only)
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
│   ├── queries.py                batched Cypher for ingestion, sync cleanup, connected shipment, peer, and precedent queries
│   └── load_graph.py             synchronized ingestion from DuckDB into Neo4j
├── rag/
│   ├── ingest_docs.py           SOP chunking, embedding, Chroma ingestion
│   └── retriever.py             embedding based retrieval and extractive answer
├── services/
│   ├── assistant_service.py     deterministic routing, fallback answers, optional SOP LLM invocation
│   ├── graph_service.py         safe Neo4j wrappers returning (result, error) pairs
│   ├── local_llm_service.py     optional Ollama SOP synthesis and validation boundary
│   └── shipment_service.py      shipment and analytics SQL queries
└── ui/
    └── streamlit_app.py          Streamlit interface

data/
├── processed/                   generated CSVs, DuckDB file, Chroma store (not committed)
├── raw/                         not currently used
└── sample_sops/                 sample SOP and FAQ markdown documents

tests/
├── test_graph.py                       graph schema, ingestion, sync, and query tests (isolated Neo4j service)
├── test_assistant_graph_routing.py     hybrid route selection, retrieval, and failure behavior
├── test_api_graph.py                   hybrid routes through /assistant/chat
├── test_docker_stack.py                compose config, container health, and cross container connections
├── test_config.py                      .env loading behavior
└── ...                                  data generation, service, routing, and API tests

docs/                             project documentation
requirements.txt                  pinned Python dependencies
Dockerfile                        one image, used by both the api and ui services
.dockerignore                     excludes generated data, .env, caches, and Git files from the image
docker-compose.yml                defines neo4j, neo4j-test, init, api, and ui
```

## Validation Commands

`docker compose config` prints the fully resolved configuration, including
the interpolated `NEO4J_AUTH` value with the local password in plain text.
Use the quiet form to validate the file without printing anything:

```bash
docker compose config --quiet
```
