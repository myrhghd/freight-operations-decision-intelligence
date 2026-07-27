# Roadmap

This roadmap tracks the project's progression from a reproducible local
baseline toward the intended retrieval and demonstration goals. Items marked
"complete" have been implemented and verified; all other items are planned
and not yet implemented.

## Milestones

1. **Repository and dependency stabilization** — complete
2. **Current assistant test coverage** — next
3. **GraphRAG foundation**
4. **Hybrid retrieval**
5. **Retrieval evaluation**
6. **Docker reproducibility**
7. **Portfolio demonstration**

## Completed Functionality

- Synthetic data generation for carriers, customers, routes, shipments,
  shipment events, and exceptions, with a fixed random seed for
  reproducibility.
- DuckDB database build and load with basic row-count and referential
  validation.
- FastAPI backend with shipment, analytics, and assistant endpoints.
- Chroma vector store ingestion of sample SOP/FAQ documents using
  Sentence Transformers embeddings.
- Deterministic (keyword/regex-based) assistant question routing across
  shipment lookup, shipment events, delay analytics, high-risk shipments,
  and SOP search.
- Streamlit UI covering all of the above via the FastAPI backend.
- A pinned, verified-compatible `requirements.txt` and a documented local
  setup and run procedure (data generation → database build → SOP
  ingestion → API → UI).

## Current Limitations

- Assistant routing is rule-based; it does not understand phrasing outside
  its known keyword patterns and will fall back to SOP search by default.
- SOP retrieval is purely extractive: it returns matching source text
  verbatim and does not synthesize or summarize an answer.
- All data is synthetic; there is no ingestion path for real shipment or
  carrier data.
- There is no automated test suite yet (`tests/` exists but is currently
  empty).
- There is no Docker-based reproducibility path; `docker-compose.yml`
  exists but is currently empty.

## Known Technical Debt

- No automated tests covering the API routes, service-layer SQL, or the
  assistant router.
- No retrieval quality evaluation for the SOP search path (e.g., no
  labeled question/answer set to measure retrieval relevance).
- `docker-compose.yml` is present but unpopulated, which could be mistaken
  for a working containerized setup.
- The Streamlit UI hardcodes the backend base URL rather than reading it
  from configuration.

## Next Milestone: Current Assistant Test Coverage

Add automated tests for the existing, verified functionality before adding
new capabilities:

- Unit tests for `assistant_service.route_question` covering each route
  (shipment lookup, shipment events, delay analytics, high-risk shipments,
  SOP search) and its fallback behavior.
- Unit or integration tests for the shipment and analytics SQL queries in
  `shipment_service.py` against a small, known DuckDB fixture.
- Integration tests for the FastAPI endpoints (health, shipment, analytics,
  assistant) using a test client.
- A smoke test for SOP ingestion and retrieval (ingest a small fixed
  document set, confirm retrieval returns the expected source).

## Deferred Features

- **GraphRAG foundation** — introducing a graph-based representation of
  shipments, carriers, routes, and exceptions to support relationship-aware
  retrieval. Not started.
- **Hybrid retrieval** — combining vector search with structured/graph
  queries for questions that need both SOP text and shipment-relationship
  context. Not started.
- **Retrieval evaluation** — a repeatable process for measuring retrieval
  quality (e.g., precision on a labeled question set) once GraphRAG and/or
  hybrid retrieval exist. Not started.
- **Docker reproducibility** — populating `docker-compose.yml` and adding
  Dockerfiles so the full stack (API, UI, and any future services) can run
  in containers. Not started.
- **Portfolio demonstration** — packaging the project (documentation,
  sample walkthroughs, and any recorded demo) for external presentation
  once the above milestones are complete. Not started.
- **Generative language model integration** — explicitly out of scope for
  the current phase; no generative LLM is used anywhere in the system
  today.
