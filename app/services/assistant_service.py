from __future__ import annotations

import logging
import re
from typing import Any

from app.core import config
from app.rag.retriever import extractive_answer_from_chunks, retrieve_sop_chunks
from app.schemas.local_llm import LLMEvidence, SOPGenerationRequest, SOPGenerationResult
from app.services.graph_service import (
    get_exception_precedents,
    get_peer_shipments,
    get_shipment_graph_context,
)
from app.services.shipment_service import (
    get_delay_rates,
    get_high_risk_shipments,
    get_shipment_details,
    get_shipment_events,
)


SHIPMENT_ID_PATTERN = re.compile(r"\bSHP-\d{4,}\b", flags=re.IGNORECASE)
logger = logging.getLogger(__name__)
MAX_LLM_EVIDENCE_CHUNKS = 3
MAX_LLM_INPUT_CHARS = 6000


def _get_llm_service():
    from app.services.local_llm_service import OllamaLLMService

    return OllamaLLMService()


def _render_sop_selection(
    response: dict[str, Any], evidence: list[LLMEvidence], result: SOPGenerationResult,
) -> dict[str, Any]:
    by_id = {item.evidence_id: item for item in evidence}
    selected = [by_id[evidence_id] for evidence_id in result.selected_evidence_ids]
    return {
        **response,
        "answer": "\n\n".join(item.text for item in selected),
        "sources": list(dict.fromkeys(item.source for item in selected)),
    }


def _enhance_sop_response(response: dict[str, Any]) -> dict[str, Any]:
    if not config.LOCAL_LLM_ENABLED:
        return response
    try:
        chunks = response["data"]
        if not chunks or len(chunks) > MAX_LLM_EVIDENCE_CHUNKS:
            return response
        evidence = [
            LLMEvidence(evidence_id=f"e{index}", source=chunk["source"], text=chunk["text"])
            for index, chunk in enumerate(chunks, start=1)
            if isinstance(chunk.get("text"), str) and chunk["text"].strip()
            and isinstance(chunk.get("source"), str) and chunk["source"].strip()
        ]
        if not evidence:
            return response
        request = SOPGenerationRequest(question=response["question"], evidence=evidence)
        # Bound the serialized input without truncating passages or their conditions.
        if len(request.model_dump_json()) > MAX_LLM_INPUT_CHARS:
            return response
        logger.info("SOP LLM enhancement attempted")
        selection = _get_llm_service().select_sop_evidence(request)
        # Defend the rendering boundary even if a replacement service is malformed.
        result = SOPGenerationResult.model_validate(selection.model_dump())
        enhanced = _render_sop_selection(response, evidence, result)
        logger.info("SOP LLM enhancement succeeded")
        return enhanced
    except Exception:
        # Preserve the exact deterministic result and omit payloads/error details.
        logger.warning("SOP LLM fallback used because generation failed")
        return response


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
    graph_sop_terms = ("procedure", "sop", "escalation", "operating procedure", "which policy")
    graph_precedent_terms = (
        "precedent",
        "seen this exception before",
        "seen this exceptions before",
        "happened before",
        "same exception type",
        "resolved before",
    )
    graph_peer_terms = (
        "same carrier and route",
        "share the same carrier",
        "share the same route",
        "similar shipments",
        "risk pattern",
    )
    graph_explanation_terms = ("why is", "why was", "explain", "reason for", "what caused")
    delay_analytics_terms = ("delay rate", "delay rates", "lanes", "carrier performance", "highest delay")
    high_risk_terms = ("high-risk", "high risk", "risk", "exceptions", "at risk")

    if shipment_id and any(term in text for term in shipment_lookup_terms):
        return "shipment_lookup"
    if shipment_id and any(term in text for term in shipment_events_terms):
        return "shipment_events"
    if shipment_id and any(term in text for term in graph_sop_terms):
        return "graph_sop_explanation"
    if shipment_id and any(term in text for term in graph_precedent_terms):
        return "graph_exception_precedents"
    if shipment_id and any(term in text for term in graph_peer_terms):
        return "graph_peer_shipments"
    if shipment_id and any(term in text for term in graph_explanation_terms):
        return "graph_shipment_explanation"
    if any(term in text for term in delay_analytics_terms):
        return "delay_analytics"
    if any(term in text for term in high_risk_terms):
        return "high_risk_shipments"
    return "sop_search"


def _empty_graph_data() -> dict[str, Any]:
    return {
        "shipment": None,
        "graph_context": None,
        "peers": [],
        "precedents": [],
        "sop_guidance": None,
    }


def _missing_shipment_id_response(question: str, route: str) -> dict[str, Any]:
    return {
        "question": question,
        "route": route,
        "answer": "No shipment ID found in the question.",
        "data": _empty_graph_data(),
        "sources": [],
        "retrieval_sources": [],
    }


def _unknown_shipment_response(question: str, route: str, shipment_id: str) -> dict[str, Any]:
    return {
        "question": question,
        "route": route,
        "answer": f"Shipment '{shipment_id}' was not found.",
        "data": _empty_graph_data(),
        "sources": [],
        "retrieval_sources": [],
    }


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

    if route == "graph_shipment_explanation":
        if shipment_id is None:
            return _missing_shipment_id_response(question, route)
        shipment = get_shipment_details(shipment_id)
        if shipment is None:
            return _unknown_shipment_response(question, route, shipment_id)

        data = _empty_graph_data()
        data["shipment"] = shipment
        retrieval_sources = ["duckdb"]

        context, error = get_shipment_graph_context(shipment_id)
        if error:
            answer = (
                f"Shipment {shipment_id} is {shipment.get('shipment_status')}. {error}"
            )
        elif context is None:
            answer = (
                f"Shipment {shipment_id} is {shipment.get('shipment_status')}. "
                "No graph data is available for this shipment yet."
            )
        else:
            data["graph_context"] = context
            retrieval_sources.append("neo4j")
            event_count = len(context["events"])
            exception = context.get("exception")
            if exception:
                answer = (
                    f"Shipment {shipment_id} is {shipment.get('shipment_status')} with "
                    f"{event_count} recorded events. It has an active exception: "
                    f"{exception.get('exception_type')} ({exception.get('severity')})."
                )
            else:
                answer = (
                    f"Shipment {shipment_id} is {shipment.get('shipment_status')} with "
                    f"{event_count} recorded events and no recorded exception."
                )
        return {
            "question": question,
            "route": route,
            "answer": answer,
            "data": data,
            "sources": [],
            "retrieval_sources": retrieval_sources,
        }

    if route == "graph_peer_shipments":
        if shipment_id is None:
            return _missing_shipment_id_response(question, route)
        shipment = get_shipment_details(shipment_id)
        if shipment is None:
            return _unknown_shipment_response(question, route, shipment_id)

        data = _empty_graph_data()
        data["shipment"] = shipment
        retrieval_sources = ["duckdb"]

        peers, error = get_peer_shipments(shipment_id, limit=10)
        if error:
            answer = (
                f"Shipment {shipment_id} was found, but peer shipment data is currently "
                "unavailable."
            )
        else:
            retrieval_sources.append("neo4j")
            data["peers"] = peers
            if not peers:
                answer = (
                    f"No other shipments share the same carrier and route as {shipment_id}."
                )
            else:
                delayed_count = sum(1 for peer in peers if peer.get("is_delayed"))
                answer = (
                    f"Found {len(peers)} shipment(s) sharing the same carrier and route as "
                    f"{shipment_id}; {delayed_count} of them are currently delayed."
                )
        return {
            "question": question,
            "route": route,
            "answer": answer,
            "data": data,
            "sources": [],
            "retrieval_sources": retrieval_sources,
        }

    if route == "graph_exception_precedents":
        if shipment_id is None:
            return _missing_shipment_id_response(question, route)
        shipment = get_shipment_details(shipment_id)
        if shipment is None:
            return _unknown_shipment_response(question, route, shipment_id)

        data = _empty_graph_data()
        data["shipment"] = shipment
        retrieval_sources = ["duckdb"]

        if not shipment.get("exception_flag"):
            answer = (
                f"Shipment {shipment_id} has no recorded exception, so there is no "
                "precedent to look up."
            )
            return {
                "question": question,
                "route": route,
                "answer": answer,
                "data": data,
                "sources": [],
                "retrieval_sources": retrieval_sources,
            }

        precedents, error = get_exception_precedents(shipment_id, limit=10)
        if error:
            answer = (
                f"Shipment {shipment_id} has an exception, but precedent data is "
                "currently unavailable."
            )
        else:
            retrieval_sources.append("neo4j")
            data["precedents"] = precedents
            if not precedents:
                answer = (
                    "No prior shipments with the same exception type were found on "
                    "this carrier or route."
                )
            else:
                resolved_count = sum(
                    1 for item in precedents if item.get("resolution_status") == "Resolved"
                )
                answer = (
                    f"Found {len(precedents)} prior shipment(s) with the same exception "
                    f"type on this carrier or route; {resolved_count} were resolved."
                )
        return {
            "question": question,
            "route": route,
            "answer": answer,
            "data": data,
            "sources": [],
            "retrieval_sources": retrieval_sources,
        }

    if route == "graph_sop_explanation":
        if shipment_id is None:
            return _missing_shipment_id_response(question, route)
        shipment = get_shipment_details(shipment_id)
        if shipment is None:
            return _unknown_shipment_response(question, route, shipment_id)

        data = _empty_graph_data()
        data["shipment"] = shipment
        retrieval_sources = ["duckdb"]

        context, error = get_shipment_graph_context(shipment_id)
        if error:
            answer = (
                f"Shipment {shipment_id} was found, but graph context is currently "
                "unavailable, so SOP guidance could not be confirmed."
            )
            return {
                "question": question,
                "route": route,
                "answer": answer,
                "data": data,
                "sources": [],
                "retrieval_sources": retrieval_sources,
            }

        data["graph_context"] = context
        retrieval_sources.append("neo4j")

        exception = context.get("exception") if context else None
        if not exception:
            answer = f"Shipment {shipment_id} has no recorded exception, so no specific SOP applies."
            return {
                "question": question,
                "route": route,
                "answer": answer,
                "data": data,
                "sources": [],
                "retrieval_sources": retrieval_sources,
            }

        exception_type = exception.get("exception_type", "")
        try:
            chunks = retrieve_sop_chunks(question=exception_type, top_k=3)
            sop_result = extractive_answer_from_chunks(question=exception_type, chunks=chunks)
        except Exception:
            answer = (
                f"Shipment {shipment_id} has a {exception_type} exception, but SOP "
                "retrieval is currently unavailable."
            )
            return {
                "question": question,
                "route": route,
                "answer": answer,
                "data": data,
                "sources": [],
                "retrieval_sources": retrieval_sources,
            }

        retrieval_sources.append("chroma")
        sources = sop_result.get("sources", [])
        data["sop_guidance"] = {"answer": sop_result.get("answer", ""), "sources": sources}
        answer = (
            f"Shipment {shipment_id} has a {exception_type} exception. "
            f"{sop_result.get('answer', '')}"
        ).strip()
        return {
            "question": question,
            "route": route,
            "answer": answer,
            "data": data,
            "sources": sources,
            "retrieval_sources": retrieval_sources,
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

    try:
        chunks = retrieve_sop_chunks(question=question, top_k=3)
    except Exception:
        return {
            "question": question,
            "route": route,
            "answer": "SOP retrieval is currently unavailable.",
            "data": [],
            "sources": [],
        }

    sop_result = extractive_answer_from_chunks(question=question, chunks=chunks)
    response = {
        "question": question,
        "route": route,
        "answer": sop_result.get("answer", ""),
        "data": chunks,
        "sources": sop_result.get("sources", []),
    }
    return _enhance_sop_response(response)
