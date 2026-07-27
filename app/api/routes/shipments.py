from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.shipment_service import get_shipment_details, get_shipment_events


router = APIRouter(prefix="/shipments", tags=["shipments"])


@router.get("/{shipment_id}")
def read_shipment(shipment_id: str) -> dict:
    shipment = get_shipment_details(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found.")
    return shipment


@router.get("/{shipment_id}/events")
def read_shipment_events(shipment_id: str) -> list[dict]:
    shipment = get_shipment_details(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found.")
    return get_shipment_events(shipment_id)
