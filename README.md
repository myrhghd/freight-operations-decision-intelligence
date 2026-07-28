# Freight Visibility AI Assistant

Local first freight visibility tool for tracking shipments, monitoring delays,
and surfacing high risk shipments across carriers, lanes, and customers.
Includes an SOP and FAQ assistant that answers operational questions using
retrieval over a set of standard operating procedure documents.

## Current capabilities

- Shipment lookup and event timeline retrieval.
- Delay rate analytics by carrier and lane.
- High risk shipment surfacing (delayed, flagged with an exception, or on a
  lane with a historically high delay rate).
- SOP and FAQ retrieval over a fixed set of markdown documents using vector
  search.
- A rule based assistant router that maps a natural language question to one
  of the above capabilities (shipment lookup, shipment events, delay
  analytics, high risk shipments, or SOP search) using keyword matching and
  shipment ID pattern detection.
- A Streamlit interface covering all of the above, backed by the FastAPI
  service.

## Architecture summary

- **Data layer**: synthetic shipment, carrier, customer, route, event, and
  exception data generated with NumPy and Pandas and loaded into a local
  DuckDB database file.
- **API layer**: FastAPI service (`app/api`) exposing shipment, analytics,
  and assistant endpoints. Reads are served from DuckDB through read only
  connections.
- **Retrieval layer**: SOP and FAQ markdown documents are chunked, embedded
  with a Sentence Transformers model (`all-MiniLM-L6-v2`), and stored in a
  local Chroma vector store (`app/rag`). Retrieval returns the matching
  chunks directly rather than generating new text.
- **Assistant routing**: `app/services/assistant_service.py` uses pattern and
  keyword matching to route a question to a shipment lookup, an analytics
  query, or SOP retrieval. Routing is deterministic rather than model
  driven.
- **UI layer**: Streamlit app (`app/ui/streamlit_app.py`) that calls the
  FastAPI service over HTTP.

## Python version

Python 3.11

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

No environment variables are required for local use (see `.env.example`).

## Running with Docker

The complete application (FastAPI, Streamlit, and Neo4j) can run with one
command. Copy `.env.example` to `.env` first and set a real password for
`NEO4J_PASSWORD`.

Start everything:

```bash
docker compose up --build
```

This starts Neo4j, waits for it to become healthy, then runs a one time
setup step that generates synthetic data, builds the DuckDB database,
ingests the SOP documents into Chroma, and loads the Neo4j graph, before
starting the API and the Streamlit UI.

Verify it is running:

```bash
docker compose ps
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/graph
curl -I http://127.0.0.1:8501
```

The API is on `http://127.0.0.1:8000` and the Streamlit UI is on
`http://127.0.0.1:8501`.

Stop everything:

```bash
docker compose down
```

This stops and removes the containers but keeps the named volumes, so the
generated data, Chroma store, and Neo4j graph are still there the next time
you run `docker compose up --build`.

## Running locally with Python

Run these steps in order from the project root, with the virtual environment
activated.

### 1. Generate synthetic data

```bash
python -m app.data.generate_synthetic_data
```

Writes `carriers.csv`, `customers.csv`, `routes.csv`, `shipments.csv`,
`shipment_events.csv`, and `exceptions.csv` to `data/processed/`.

### 2. Build the DuckDB database

```bash
python -m app.data.load_data
```

Loads the generated CSVs into `data/processed/logistics.duckdb`.

### 3. Ingest SOP documents into Chroma

```bash
python -m app.rag.ingest_docs
```

Chunks the markdown files in `data/sample_sops/`, embeds them with
`sentence-transformers/all-MiniLM-L6-v2`, and stores them in a local Chroma
collection under `data/processed/chroma/`. The first run downloads the
embedding model from Hugging Face and caches it locally; later runs work
offline.

### 4. Start the FastAPI service

```bash
uvicorn app.api.main:app --reload
```

Runs on `http://127.0.0.1:8000` by default.

### 5. Start the Streamlit app

In a separate terminal, with the same virtual environment activated:

```bash
streamlit run app/ui/streamlit_app.py
```

The Streamlit app expects the FastAPI service to be running on
`http://127.0.0.1:8000`.

## Example API endpoints

- `GET /health`
- `GET /shipments/{shipment_id}`
- `GET /shipments/{shipment_id}/events`
- `GET /analytics/delay-rates`
- `GET /analytics/high-risk-shipments?limit=50`
- `POST /assistant/sop-search` (request body: `{"question": "..."}`)
- `POST /assistant/chat` (request body: `{"question": "..."}`)

## Retrieval evaluation

A labeled question set checks assistant routing and SOP retrieval quality
against the local database, Neo4j, and Chroma store. Run it with:

```bash
python evaluation/evaluate.py
```

It reports:

- Routing accuracy: how often the assistant selects the expected route.
- Shipment ID extraction accuracy: how often the expected shipment ID is
  extracted from the question text.
- SOP source hit rate: for questions with an expected SOP document, how
  often that document appears in the returned sources.
- Route confusion counts: for any routing mismatch, the expected route and
  the route actually chosen.
- Failed cases: the question, category, and expected versus actual values
  for anything that did not match.

The script exits with a nonzero status when a result falls below its
documented threshold. Latest verified run, against the local dev database,
Neo4j, and Chroma store, over 54 questions:

- Routing accuracy: 100.0% (threshold 95%)
- Shipment ID extraction accuracy: 100.0% (threshold 95%)
- SOP source hit rate: 100.0%, 10 questions with an expected source
  (threshold 85%)
- Route confusion: none
- Failed cases: none

## Current limitations

- All shipment, carrier, customer, and route data is synthetic, generated
  locally with a fixed random seed. It does not represent real freight data.
- Assistant routing is deterministic, based on keywords and patterns rather
  than a model.
- SOP retrieval returns matching text directly rather than generating a new
  answer.
- Generated CSVs, the DuckDB database file, and the Chroma vector store are
  local build artifacts and are not committed to version control.
