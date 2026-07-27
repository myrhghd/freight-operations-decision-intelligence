# Architecture

This document describes the current system as verified in this repository.

## Components

### FastAPI backend (`app/api`)

Exposes the HTTP API consumed by the Streamlit interface:

- `GET /health`
- `GET /shipments/{shipment_id}`
- `GET /shipments/{shipment_id}/events`
- `GET /analytics/delay-rates`
- `GET /analytics/high-risk-shipments`
- `POST /assistant/sop-search`
- `POST /assistant/chat`

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
```

## Repository Structure

```
app/
├── api/
│   ├── main.py                 FastAPI app and /health endpoint
│   └── routes/                 shipments, analytics, assistant routers
├── core/
│   └── config.py                project paths and service name constant
├── data/
│   ├── generate_synthetic_data.py
│   └── load_data.py
├── db/
│   └── connection.py            DuckDB read only connection helpers
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

docs/                             project documentation
requirements.txt                  pinned Python dependencies
docker-compose.yml                present in the repository; does not define any services
```
