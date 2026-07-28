from __future__ import annotations

import json
from pathlib import Path

import pytest

import evaluation.evaluate as evaluate_module

QUESTIONS_PATH = Path(__file__).resolve().parents[1] / "evaluation" / "questions.json"
SOP_DOCS_DIR = Path(__file__).resolve().parents[1] / "data" / "sample_sops"

VALID_ROUTES = {
    "shipment_lookup",
    "shipment_events",
    "delay_analytics",
    "high_risk_shipments",
    "sop_search",
    "graph_shipment_explanation",
    "graph_peer_shipments",
    "graph_exception_precedents",
    "graph_sop_explanation",
}


def _load_questions() -> list[dict]:
    return json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))


# --- evaluation dataset schema ---


def test_questions_dataset_is_not_empty() -> None:
    assert len(_load_questions()) > 0


def test_questions_dataset_has_valid_schema() -> None:
    for record in _load_questions():
        assert isinstance(record["question"], str) and record["question"].strip()
        assert record["expected_route"] in VALID_ROUTES
        assert record["expected_shipment_id"] is None or isinstance(
            record["expected_shipment_id"], str
        )
        assert record["expected_sop_source"] is None or isinstance(
            record["expected_sop_source"], str
        )


def test_questions_dataset_covers_every_route() -> None:
    covered_routes = {record["expected_route"] for record in _load_questions()}
    assert covered_routes == VALID_ROUTES


def test_questions_dataset_shipment_ids_match_pattern() -> None:
    for record in _load_questions():
        shipment_id = record["expected_shipment_id"]
        if shipment_id is not None:
            assert shipment_id.startswith("SHP-")


def test_questions_dataset_sop_sources_are_real_files() -> None:
    real_sop_files = {path.name for path in SOP_DOCS_DIR.glob("*.md")}
    assert real_sop_files, "expected sample SOP files to exist"
    for record in _load_questions():
        sop_source = record["expected_sop_source"]
        if sop_source is not None:
            assert sop_source in real_sop_files


# --- evaluation script metrics ---

pytestmark = pytest.mark.usefixtures("require_neo4j")


def test_evaluate_returns_expected_metric_keys(ingested_graph: dict[str, int]) -> None:
    results = evaluate_module.evaluate()
    assert set(results.keys()) == {
        "total_questions",
        "routing_accuracy",
        "shipment_id_accuracy",
        "sop_source_hit_rate",
        "sop_source_questions",
        "route_confusion",
        "failed_cases",
    }
    assert results["total_questions"] == len(_load_questions())


def test_evaluate_meets_documented_thresholds(ingested_graph: dict[str, int]) -> None:
    results = evaluate_module.evaluate()
    assert results["routing_accuracy"] >= evaluate_module.ROUTING_ACCURACY_THRESHOLD
    assert results["shipment_id_accuracy"] >= evaluate_module.SHIPMENT_ID_ACCURACY_THRESHOLD
    assert results["sop_source_hit_rate"] >= evaluate_module.SOP_SOURCE_HIT_RATE_THRESHOLD
    assert results["failed_cases"] == []


def test_main_returns_zero_when_thresholds_are_met(ingested_graph: dict[str, int]) -> None:
    assert evaluate_module.main() == 0


def test_evaluate_reports_confusion_and_failed_case_for_mismatch(
    ingested_graph: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "evaluation.evaluate.load_questions",
        lambda: [
            {
                "category": "test",
                "question": "What is the status of SHP-1001?",
                "expected_route": "shipment_events",
                "expected_shipment_id": "SHP-1001",
                "expected_sop_source": None,
            }
        ],
    )
    results = evaluate_module.evaluate()
    assert results["routing_accuracy"] == 0.0
    assert results["route_confusion"][("shipment_events", "shipment_lookup")] == 1
    assert len(results["failed_cases"]) == 1
    assert results["failed_cases"][0]["expected_route"] == "shipment_events"
    assert results["failed_cases"][0]["actual_route"] == "shipment_lookup"
