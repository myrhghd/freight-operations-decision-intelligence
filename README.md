# Freight Visibility AI Assistant

Local-first freight visibility tool for tracking shipments, monitoring delays, and
surfacing high-risk shipments across carriers, lanes, and customers. Includes an
SOP/FAQ assistant that answers operational questions using retrieval over a small
set of standard operating procedure documents.

## Current capabilities

- Shipment lookup and event-timeline retrieval.
- Delay-rate analytics by carrier and lane.
- High-risk shipment surfacing (delayed, exception-flagged, or historically
  high-delay-rate lanes).
- SOP/FAQ retrieval over a fixed set of markdown documents using vector search.
- A rule-based assistant router that maps a natural-language question to one of
  the above capabilities (shipment lookup, shipment events, delay analytics,
  high-risk shipments, or SOP search) using keyword matching and shipment-ID
  pattern detection.
- A Streamlit UI covering all of the above, backed by the FastAPI service.

## Architecture summary

- **Data layer**: synthetic shipment, carrier, customer, route, event, and
  exception data generated with NumPy/Pandas and loaded into a local DuckDB
  database file.
- **API layer**: FastAPI service (`app/api`) exposing shipment, analytics, and
  assistant endpoints. Reads are served from DuckDB via read-only connections.
- **Retrieval layer**: SOP/FAQ markdown documents are chunked, embedded with a
  Sentence Transformers model (`all-MiniLM-L6-v2`), and stored in a local
  Chroma vector store (`app/rag`). Retrieval returns the top matching chunks
  verbatim (extractive), with no generative model in the loop.
- **Assistant routing**: `app/services/assistant_service.py` uses regex and
  keyword matching to route a question to a shipment lookup, an analytics
  query, or SOP retrieval. This is deterministic, not model-driven.
- **UI layer**: Streamlit app (`app/ui/streamlit_app.py`) that calls the FastAPI
  service over HTTP.

## Python version

Verified against **Python 3.11** on macOS (Intel/x86_64).

> Note: on Intel macOS, PyTorch does not publish wheels newer than `2.2.2`,
> which in turn requires NumPy `<2.0`. `requirements.txt` pins compatible
> versions of NumPy, PyTorch, Transformers, and Sentence Transformers that are
> verified to import and run together. If you install on a different platform
> (Apple Silicon, Linux, Windows), keep these pins unless you re-verify a
> different combination.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

No environment variables are required for local use (see `.env.example`).

## Running the application

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
embedding model from Hugging Face and caches it locally; subsequent runs
work offline.

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
`http://127.0.0.1:8000` (see `API_BASE_URL` in `app/ui/streamlit_app.py`).

## Example API endpoints

- `GET /health`
- `GET /shipments/{shipment_id}`
- `GET /shipments/{shipment_id}/events`
- `GET /analytics/delay-rates`
- `GET /analytics/high-risk-shipments?limit=50`
- `POST /assistant/sop-search` — body: `{"question": "..."}`
- `POST /assistant/chat` — body: `{"question": "..."}`

## Current limitations

- All shipment, carrier, customer, and route data is **synthetic**, generated
  locally with a fixed random seed. It does not represent real freight data.
- Assistant routing is **deterministic** (keyword and regex based), not model
  driven.
- SOP retrieval uses **vector search** over a small, fixed set of sample SOP
  documents and returns matching text chunks directly (extractive). It does
  not generate new text.
- **No generative LLM or GraphRAG is implemented.** The assistant does not call
  any external or local language model; it returns retrieved or queried data
  directly.
- Generated CSVs, the DuckDB database file, and the Chroma vector store are
  local build artifacts and are not committed to version control.
