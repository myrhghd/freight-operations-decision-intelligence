from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.assistant_service import build_chat_response, find_shipment_id  # noqa: E402

QUESTIONS_PATH = Path(__file__).resolve().parent / "questions.json"

# Verified against the local dev database, Neo4j, and Chroma store on the date
# this suite was written (see README.md for the latest recorded run). Set
# below what was actually achieved rather than a perfect score, so a future
# regression that is still reasonably close does not fail the build outright.
ROUTING_ACCURACY_THRESHOLD = 0.95
SHIPMENT_ID_ACCURACY_THRESHOLD = 0.95
SOP_SOURCE_HIT_RATE_THRESHOLD = 0.85


def load_questions() -> list[dict[str, Any]]:
    return json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))


def evaluate() -> dict[str, Any]:
    questions = load_questions()

    route_total = 0
    route_correct = 0
    shipment_id_total = 0
    shipment_id_correct = 0
    sop_total = 0
    sop_hits = 0
    route_confusion: Counter[tuple[str, str]] = Counter()
    failed_cases: list[dict[str, Any]] = []

    for record in questions:
        question = record["question"]
        expected_route = record["expected_route"]
        expected_shipment_id = record.get("expected_shipment_id")
        expected_sop_source = record.get("expected_sop_source")

        response = build_chat_response(question)
        actual_route = response.get("route")
        actual_shipment_id = find_shipment_id(question)
        actual_sources = response.get("sources") or []

        route_total += 1
        route_ok = actual_route == expected_route
        if route_ok:
            route_correct += 1
        else:
            route_confusion[(expected_route, actual_route)] += 1

        shipment_id_total += 1
        shipment_id_ok = actual_shipment_id == expected_shipment_id
        if shipment_id_ok:
            shipment_id_correct += 1

        sop_ok = True
        if expected_sop_source is not None:
            sop_total += 1
            sop_ok = expected_sop_source in actual_sources
            if sop_ok:
                sop_hits += 1

        if not (route_ok and shipment_id_ok and sop_ok):
            failed_cases.append(
                {
                    "question": question,
                    "category": record.get("category"),
                    "expected_route": expected_route,
                    "actual_route": actual_route,
                    "expected_shipment_id": expected_shipment_id,
                    "actual_shipment_id": actual_shipment_id,
                    "expected_sop_source": expected_sop_source,
                    "actual_sources": actual_sources if expected_sop_source is not None else None,
                }
            )

    routing_accuracy = route_correct / route_total if route_total else 0.0
    shipment_id_accuracy = shipment_id_correct / shipment_id_total if shipment_id_total else 0.0
    sop_source_hit_rate = sop_hits / sop_total if sop_total else 1.0

    return {
        "total_questions": route_total,
        "routing_accuracy": routing_accuracy,
        "shipment_id_accuracy": shipment_id_accuracy,
        "sop_source_hit_rate": sop_source_hit_rate,
        "sop_source_questions": sop_total,
        "route_confusion": route_confusion,
        "failed_cases": failed_cases,
    }


def print_report(results: dict[str, Any]) -> None:
    print(f"Evaluated {results['total_questions']} questions")
    print(f"Routing accuracy: {results['routing_accuracy']:.1%}")
    print(f"Shipment ID extraction accuracy: {results['shipment_id_accuracy']:.1%}")
    print(
        f"SOP source hit rate: {results['sop_source_hit_rate']:.1%} "
        f"({results['sop_source_questions']} questions with an expected source)"
    )

    print("\nRoute confusion (expected -> actual: count):")
    if results["route_confusion"]:
        for (expected, actual), count in results["route_confusion"].most_common():
            print(f"  {expected} -> {actual}: {count}")
    else:
        print("  none")

    print(f"\nFailed cases: {len(results['failed_cases'])}")
    for case in results["failed_cases"]:
        print(f"  [{case['category']}] {case['question']!r}")
        if case["actual_route"] != case["expected_route"]:
            print(f"    route: expected {case['expected_route']!r}, got {case['actual_route']!r}")
        if case["actual_shipment_id"] != case["expected_shipment_id"]:
            print(
                f"    shipment_id: expected {case['expected_shipment_id']!r}, "
                f"got {case['actual_shipment_id']!r}"
            )
        if case["expected_sop_source"] is not None:
            print(
                f"    sop_source: expected {case['expected_sop_source']!r} "
                f"in {case['actual_sources']!r}"
            )


def main() -> int:
    results = evaluate()
    print_report(results)

    passed = (
        results["routing_accuracy"] >= ROUTING_ACCURACY_THRESHOLD
        and results["shipment_id_accuracy"] >= SHIPMENT_ID_ACCURACY_THRESHOLD
        and results["sop_source_hit_rate"] >= SOP_SOURCE_HIT_RATE_THRESHOLD
    )

    print("\nThresholds:")
    print(f"  routing_accuracy >= {ROUTING_ACCURACY_THRESHOLD:.0%}")
    print(f"  shipment_id_accuracy >= {SHIPMENT_ID_ACCURACY_THRESHOLD:.0%}")
    print(f"  sop_source_hit_rate >= {SOP_SOURCE_HIT_RATE_THRESHOLD:.0%}")
    print(f"Result: {'PASS' if passed else 'FAIL'}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
