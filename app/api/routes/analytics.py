from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.shipment_service import get_delay_rates, get_high_risk_shipments


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/delay-rates")
def read_delay_rates() -> list[dict]:
    return get_delay_rates()


@router.get("/high-risk-shipments")
def read_high_risk_shipments(limit: int = Query(default=50, ge=1)) -> list[dict]:
    return get_high_risk_shipments(limit=limit)
