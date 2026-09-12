from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.ui.streamlit_app import (
    ASSISTANT_REQUEST_TIMEOUT_SECONDS,
    call_api_post,
    carrier_context_rows,
    events_dataframe,
    exception_detail_rows,
    field_label,
    records_dataframe,
    render_hybrid_response,
    retrieval_sources_label,
    route_context_rows,
    shipment_summary_rows,
    sop_guidance_text,
)


def test_assistant_timeout_covers_cold_local_inference() -> None:
    assert ASSISTANT_REQUEST_TIMEOUT_SECONDS == 130


@patch("app.ui.streamlit_app.requests.post")
def test_post_helper_accepts_assistant_timeout(post) -> None:
    post.return_value.status_code = 200
    post.return_value.json.return_value = {"status": "ok"}
    assert call_api_post("/assistant/chat", {"question": "Policy?"}, timeout=130) == (
        {"status": "ok"}, None, 200
    )
    post.assert_called_once_with(
        "http://127.0.0.1:8000/assistant/chat",
        json={"question": "Policy?"},
        timeout=130,
    )

SHIPMENT = {
    "shipment_id": "SHP-1021",
    "shipment_status": "DELIVERED_LATE",
    "shipment_mode": "Truckload",
    "is_delayed": True,
    "delay_days": 1,
    "exception_flag": True,
    "customer_name": "Granite Distribution 9",
    "customer_tier": "Growth",
    "carrier_name": "NorthStar Freight",
    "carrier_type": "FTL",
    "origin_city": "Seattle",
    "origin_state": "WA",
    "destination_city": "Kansas City",
    "destination_state": "MO",
    "planned_delivery_date": "2025-07-20",
    "actual_delivery_date": "2025-07-21",
}

GRAPH_CONTEXT = {
    "shipment": {"shipment_id": "SHP-1021"},
    "carrier": {
        "carrier_id": "CAR-001",
        "carrier_name": "NorthStar Freight",
        "carrier_type": "FTL",
        "on_time_rate": 0.944,
        "risk_score": 21.3,
    },
    "customer": {
        "customer_id": "CUS-009",
        "customer_name": "Granite Distribution 9",
        "customer_tier": "Growth",
    },
    "route": {
        "route_id": "RTE-010",
        "origin_city": "Seattle",
        "origin_state": "WA",
        "destination_city": "Kansas City",
        "destination_state": "MO",
        "historical_delay_rate": 0.231,
    },
    "exception": {
        "exception_id": "EXC-00001",
        "exception_type": "Missed appointment",
        "severity": "Low",
        "resolution_status": "Resolved",
        "detected_at": "2025-07-19 19:00:00",
    },
    "events": [
        {
            "event_id": "EVT-000099",
            "event_type": "DELIVERED",
            "event_city": "Kansas City",
            "event_state": "MO",
            "event_timestamp": "2025-07-21 03:00:00",
        },
        {
            "event_id": "EVT-000094",
            "event_type": "CREATED",
            "event_city": "Seattle",
            "event_state": "WA",
            "event_timestamp": "2025-07-18 00:00:00",
        },
    ],
}

PEERS = [
    {
        "shipment_id": "SHP-1050",
        "shipment_status": "DELIVERED",
        "is_delayed": False,
        "delay_days": 0,
        "exception_flag": False,
        "exception_type": None,
    },
]

PRECEDENTS = [
    {
        "shipment_id": "SHP-1099",
        "exception_type": "Missed appointment",
        "severity": "Low",
        "resolution_status": "Resolved",
        "detected_at": "2025-06-01 10:00:00",
    },
]

SOP_GUIDANCE = {
    "answer": "Escalate from Level 1 to Level 2 at the 45 minute no response mark.",
    "sources": ["carrier_escalation_matrix.md"],
}

FULL_RESULT = {
    "question": "Which operating procedure applies to SHP-1021's exception?",
    "route": "graph_sop_explanation",
    "answer": "Shipment SHP-1021 has a Missed appointment exception.",
    "data": {
        "shipment": SHIPMENT,
        "graph_context": GRAPH_CONTEXT,
        "peers": PEERS,
        "precedents": PRECEDENTS,
        "sop_guidance": SOP_GUIDANCE,
    },
    "sources": ["carrier_escalation_matrix.md"],
    "retrieval_sources": ["duckdb", "neo4j", "chroma"],
}

EMPTY_RESULT = {
    "question": "Which shipments share the same carrier and route as SHP-1001?",
    "route": "graph_peer_shipments",
    "answer": "No other shipments share the same carrier and route as SHP-1001.",
    "data": {
        "shipment": {**SHIPMENT, "shipment_id": "SHP-1001"},
        "graph_context": {**GRAPH_CONTEXT, "events": [], "exception": None},
        "peers": [],
        "precedents": [],
        "sop_guidance": None,
    },
    "sources": [],
    "retrieval_sources": ["duckdb", "neo4j"],
}

DEGRADED_RESULT = {
    "question": "Why is SHP-1021 delayed?",
    "route": "graph_shipment_explanation",
    "answer": "Shipment SHP-1021 is DELIVERED_LATE. Neo4j is currently unavailable.",
    "data": {
        "shipment": SHIPMENT,
        "graph_context": None,
        "peers": [],
        "precedents": [],
        "sop_guidance": None,
    },
    "sources": [],
    "retrieval_sources": ["duckdb"],
}


# --- field label mapping ---


def test_field_label_uses_the_shared_mapping_for_known_fields() -> None:
    assert field_label("carrier_id") == "Carrier ID"
    assert field_label("carrier_name") == "Carrier"
    assert field_label("on_time_rate") == "On Time Rate"
    assert field_label("risk_score") == "Carrier Risk Score"
    assert field_label("route_id") == "Route ID"
    assert field_label("historical_delay_rate") == "Historical Delay Rate"
    assert field_label("shipment_id") == "Shipment ID"
    assert field_label("shipment_status") == "Status"
    assert field_label("shipment_mode") == "Transport Mode"
    assert field_label("planned_delivery_date") == "Planned Delivery"
    assert field_label("actual_delivery_date") == "Actual Delivery"
    assert field_label("delay_days") == "Delay Days"
    assert field_label("exception_type") == "Exception Type"
    assert field_label("severity") == "Severity"
    assert field_label("resolution_status") == "Resolution Status"
    assert field_label("detected_at") == "Detected At"


def test_field_label_falls_back_to_a_generated_label_for_unknown_fields() -> None:
    assert field_label("some_unlisted_field") == "Some Unlisted Field"


# --- shipment summary ---


def test_shipment_summary_rows_with_data() -> None:
    rows = shipment_summary_rows(SHIPMENT)
    assert {"Field": "Shipment ID", "Value": "SHP-1021"} in rows
    assert {"Field": "Customer", "Value": "Granite Distribution 9"} in rows


def test_shipment_summary_rows_empty_when_missing() -> None:
    assert shipment_summary_rows(None) == []


# --- carrier and route context: graph available ---


def test_carrier_context_rows_prefers_graph_context() -> None:
    rows = carrier_context_rows(SHIPMENT, GRAPH_CONTEXT)
    fields = {row["Field"] for row in rows}
    assert "Carrier Risk Score" in fields
    assert "On Time Rate" in fields


def test_route_context_rows_prefers_graph_context() -> None:
    rows = route_context_rows(SHIPMENT, GRAPH_CONTEXT)
    fields = {row["Field"] for row in rows}
    assert "Historical Delay Rate" in fields


# --- carrier and route context: existing API responses (no graph context) ---


def test_carrier_context_rows_falls_back_to_shipment_record() -> None:
    rows = carrier_context_rows(SHIPMENT, None)
    assert rows == [
        {"Field": "Carrier", "Value": "NorthStar Freight"},
        {"Field": "Carrier Type", "Value": "FTL"},
    ]


def test_route_context_rows_falls_back_to_shipment_record() -> None:
    rows = route_context_rows(SHIPMENT, None)
    assert rows == [
        {"Field": "Origin", "Value": "Seattle, WA"},
        {"Field": "Destination", "Value": "Kansas City, MO"},
    ]


def test_carrier_context_rows_empty_when_nothing_available() -> None:
    assert carrier_context_rows(None, None) == []


def test_route_context_rows_empty_when_nothing_available() -> None:
    assert route_context_rows(None, None) == []


# --- exception details ---


def test_exception_detail_rows_with_exception() -> None:
    rows = exception_detail_rows(GRAPH_CONTEXT)
    fields = {row["Field"] for row in rows}
    assert "Exception Type" in fields


def test_exception_detail_rows_no_exception_recorded() -> None:
    context_without_exception = {**GRAPH_CONTEXT, "exception": None}
    assert exception_detail_rows(context_without_exception) == []


def test_exception_detail_rows_graph_unavailable() -> None:
    assert exception_detail_rows(None) == []


# --- ordered shipment events ---


def test_events_dataframe_orders_preferred_columns_first() -> None:
    frame = events_dataframe(GRAPH_CONTEXT)
    assert list(frame.columns[:4]) == [
        "Event Timestamp",
        "Event Type",
        "Event City",
        "Event State",
    ]
    assert len(frame) == 2


def test_events_dataframe_empty_when_no_events() -> None:
    assert events_dataframe({"events": []}).empty


def test_events_dataframe_empty_when_graph_unavailable() -> None:
    assert events_dataframe(None).empty


# --- similar shipments and exception precedents ---


def test_records_dataframe_with_peers() -> None:
    frame = records_dataframe(PEERS)
    assert len(frame) == 1
    assert "Shipment ID" in frame.columns


def test_records_dataframe_with_precedents() -> None:
    frame = records_dataframe(PRECEDENTS)
    assert len(frame) == 1
    assert "Resolution Status" in frame.columns


def test_records_dataframe_empty_list() -> None:
    assert records_dataframe([]).empty


def test_records_dataframe_none() -> None:
    assert records_dataframe(None).empty


# --- SOP guidance ---


def test_sop_guidance_text_with_data() -> None:
    answer, sources = sop_guidance_text(SOP_GUIDANCE)
    assert answer == SOP_GUIDANCE["answer"]
    assert sources == ["carrier_escalation_matrix.md"]


def test_sop_guidance_text_unavailable() -> None:
    answer, sources = sop_guidance_text(None)
    assert answer == ""
    assert sources == []


# --- retrieval sources ---


def test_retrieval_sources_label_with_sources() -> None:
    assert retrieval_sources_label(["duckdb", "neo4j", "chroma"]) == "duckdb, neo4j, chroma"


def test_retrieval_sources_label_empty_list() -> None:
    assert retrieval_sources_label([]) == "No retrieval sources reported."


def test_retrieval_sources_label_none() -> None:
    assert retrieval_sources_label(None) == "No retrieval sources reported."


# --- render_hybrid_response, with Streamlit mocked out ---


def _render_with_mocked_streamlit(result: dict) -> tuple[MagicMock, list[list[MagicMock]]]:
    """Call render_hybrid_response with streamlit replaced by a mock.

    Returns the mocked streamlit module and the column mocks created by each
    st.columns() call, in call order, so tests can inspect what was rendered
    without a real Streamlit session or browser.
    """
    created_columns: list[list[MagicMock]] = []

    def _fake_columns(count: int):
        columns = [MagicMock() for _ in range(count)]
        created_columns.append(columns)
        return tuple(columns)

    with patch("app.ui.streamlit_app.st") as mock_st:
        mock_st.columns.side_effect = _fake_columns
        render_hybrid_response(result)

    return mock_st, created_columns


def test_render_hybrid_response_calls_metric_for_shipment_summary() -> None:
    mock_st, created_columns = _render_with_mocked_streamlit(FULL_RESULT)

    metric_columns = created_columns[0]
    assert len(metric_columns) == 4
    for column in metric_columns:
        assert column.metric.called

    metric_labels = [
        call.args[0] for column in metric_columns for call in column.metric.call_args_list
    ]
    assert metric_labels == ["Status", "Transport Mode", "Delayed", "Delay Days"]


def test_render_hybrid_response_calls_table_for_events_peers_and_precedents() -> None:
    mock_st, _ = _render_with_mocked_streamlit(FULL_RESULT)

    rendered_frames = [call.args[0] for call in mock_st.dataframe.call_args_list]
    assert any("Event Timestamp" in frame.columns for frame in rendered_frames)
    assert any(
        "Shipment ID" in frame.columns and "Delay Days" in frame.columns
        for frame in rendered_frames
    )
    assert any(
        "Shipment ID" in frame.columns and "Resolution Status" in frame.columns
        for frame in rendered_frames
    )


def test_render_hybrid_response_displays_sop_guidance_and_retrieval_sources() -> None:
    mock_st, _ = _render_with_mocked_streamlit(FULL_RESULT)

    written_text = [call.args[0] for call in mock_st.write.call_args_list if call.args]
    assert SOP_GUIDANCE["answer"] in written_text
    assert any("carrier_escalation_matrix.md" in text for text in written_text)
    assert any("duckdb, neo4j, chroma" in text for text in written_text)


def test_render_hybrid_response_handles_empty_graph_results_without_raising() -> None:
    mock_st, _ = _render_with_mocked_streamlit(EMPTY_RESULT)

    info_messages = [call.args[0] for call in mock_st.info.call_args_list if call.args]
    assert any("No similar shipments" in message for message in info_messages)
    assert any("No previous exception outcomes" in message for message in info_messages)
    assert any("No event data" in message for message in info_messages)
    assert not mock_st.error.called


def test_render_hybrid_response_handles_unavailable_neo4j_and_chroma_without_raising() -> None:
    mock_st, _ = _render_with_mocked_streamlit(DEGRADED_RESULT)

    info_messages = [call.args[0] for call in mock_st.info.call_args_list if call.args]
    assert any("currently unavailable" in message for message in info_messages)
    assert any("No SOP guidance" in message for message in info_messages)
    assert not mock_st.error.called


def test_render_hybrid_response_uses_the_new_user_facing_labels() -> None:
    mock_st, created_columns = _render_with_mocked_streamlit(FULL_RESULT)

    rendered_frames = [call.args[0] for call in mock_st.dataframe.call_args_list]

    # Carrier, route, and exception context render as Field/Value reference
    # tables, so their labels appear as values in the "Field" column rather
    # than as column headers.
    field_value_labels = {
        value
        for frame in rendered_frames
        if "Field" in frame.columns
        for value in frame["Field"]
    }
    assert "Carrier ID" in field_value_labels
    assert "Historical Delay Rate" in field_value_labels
    assert "Exception Type" in field_value_labels

    # Events, peers, and precedents render as wide tables, so their labels
    # appear as column headers.
    wide_table_columns = {
        column
        for frame in rendered_frames
        if "Field" not in frame.columns
        for column in frame.columns
    }
    assert "Event Timestamp" in wide_table_columns

    metric_labels = [
        call.args[0] for column in created_columns[0] for call in column.metric.call_args_list
    ]
    assert "Transport Mode" in metric_labels
