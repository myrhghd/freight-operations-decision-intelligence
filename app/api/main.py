from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.routes.analytics import router as analytics_router
from app.api.routes.assistant import router as assistant_router
from app.api.routes.shipments import router as shipments_router
from app.core.config import SERVICE_NAME
from app.graph.connection import graph_health_check


app = FastAPI(title="Freight Visibility AI Assistant API")
app.include_router(shipments_router)
app.include_router(analytics_router)
app.include_router(assistant_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
    }


@app.get("/health/graph")
def health_graph() -> JSONResponse:
    healthy = graph_health_check()
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "unavailable", "service": "neo4j"},
    )
