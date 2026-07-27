from __future__ import annotations

import re
from typing import Any

from app.rag.retriever import extractive_answer_from_chunks, retrieve_sop_chunks
from app.services.shipment_service import (
    get_delay_rates,
    get_high_risk_shipments,
    get_shipment_details,
    get_shipment_events,
)


SHIPMENT_ID_PATTERN = re.compile(r"\bSHP-\d{4,}\b", flags=re.IGNORECASE)


def find_shipment_id(question: str) -> str | None:
    match = SHIPMENT_ID_PATTERN.search(question)
    if not match:
        return None
    return match.group(0).upper()


def route_question(question: str) -> str:
    text = question.lower()
    shipment_id = find_shipment_id(question)

    shipment_lookup_terms = ("where", "status", "details")
    shipment_events_terms = ("events", "timeline", "history")
    delay_analytics_terms = ("delay rate", "delay rates", "lanes", "carrier performance", "highest delay")
    high_risk_terms = ("high-risk", "high risk", "risk", "exceptions", "at risk")

    if shipment_id and any(term in text for term in shipment_lookup_terms):
        return "shipment_lookup"
    if shipment_id and any(term in text for term in shipment_events_terms):
        return "shipment_events"
    if any(term in text for term in delay_analytics_terms):
        return "delay_analytics"
    if any(term in text for term in high_risk_terms):
        return "high_risk_shipments"
    return "sop_search"


def build_chat_response(question: str) -> dict[str, Any]:
    route = route_question(question)
    shipment_id = find_shipment_id(question)

    if route == "shipment_lookup":
        if shipment_id is None:
            return {
                "question": question,
                "route": route,
                "answer": "No shipment ID found in the question.",
                "data": None,
                "sources": [],
            }
        shipment = get_shipment_details(shipment_id)
        if shipment is None:
            return {
                "question": question,
                "route": route,
                "answer": f"Shipment '{shipment_id}' was not found.",
                "data": None,
                "sources": [],
            }
        answer = (
            f"Shipment {shipment_id} is {shipment.get('shipment_status')} from "
            f"{shipment.get('origin_city')}, {shipment.get('origin_state')} to "
            f"{shipment.get('destination_city')}, {shipment.get('destination_state')}."
        )
        return {
            "question": question,
            "route": route,
            "answer": answer,
            "data": shipment,
            "sources": [],
        }

    if route == "shipment_events":
        if shipment_id is None:
            return {
                "question": question,
                "route": route,
                "answer": "No shipment ID found in the question.",
                "data": [],
                "sources": [],
            }
        shipment = get_shipment_details(shipment_id)
        if shipment is None:
            return {
                "question": question,
                "route": route,
                "answer": f"Shipment '{shipment_id}' was not found.",
                "data": [],
                "sources": [],
            }
        events = get_shipment_events(shipment_id)
        return {
            "question": question,
            "route": route,
            "answer": f"Found {len(events)} events for shipment {shipment_id}.",
            "data": events,
            "sources": [],
        }

    if route == "delay_analytics":
        data = get_delay_rates()
        return {
            "question": question,
            "route": route,
            "answer": f"Found delay analytics for {len(data)} carrier-lane groups.",
            "data": data,
            "sources": [],
        }

    if route == "high_risk_shipments":
        data = get_high_risk_shipments(limit=50)
        return {
            "question": question,
            "route": route,
            "answer": f"Found {len(data)} high-risk shipments (top 50).",
            "data": data,
            "sources": [],
        }

    chunks = retrieve_sop_chunks(question=question, top_k=3)
    sop_result = extractive_answer_from_chunks(question=question, chunks=chunks)
    return {
        "question": question,
        "route": route,
        "answer": sop_result.get("answer", ""),
        "data": chunks,
        "sources": sop_result.get("sources", []),
    }
