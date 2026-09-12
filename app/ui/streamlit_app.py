from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
REQUEST_TIMEOUT_SECONDS = 10
# A cold local CPU model request can approach two minutes. This applies only
# to assistant chat; other API calls keep the short default timeout above.
ASSISTANT_REQUEST_TIMEOUT_SECONDS = 130

HYBRID_ROUTES = {
    "graph_shipment_explanation",
    "graph_peer_shipments",
    "graph_exception_precedents",
    "graph_sop_explanation",
}

# User facing labels for API field names shown in the hybrid response sections
# (shipment, carrier, route, exception, and event tables). Any field not
# listed here falls back to a generated label; see field_label().
FIELD_LABELS: dict[str, str] = {
    "carrier_id": "Carrier ID",
    "carrier_name": "Carrier",
    "carrier_type": "Carrier Type",
    "on_time_rate": "On Time Rate",
    "risk_score": "Carrier Risk Score",
    "route_id": "Route ID",
    "origin_city": "Origin City",
    "origin_state": "Origin State",
    "destination_city": "Destination City",
    "destination_state": "Destination State",
    "historical_delay_rate": "Historical Delay Rate",
    "shipment_id": "Shipment ID",
    "shipment_status": "Status",
    "shipment_mode": "Transport Mode",
    "planned_delivery_date": "Planned Delivery",
    "actual_delivery_date": "Actual Delivery",
    "ship_date": "Ship Date",
    "delay_days": "Delay Days",
    "is_delayed": "Delayed",
    "exception_flag": "Has Exception",
    "customer_id": "Customer ID",
    "customer_name": "Customer",
    "customer_tier": "Customer Tier",
    "exception_id": "Exception ID",
    "exception_type": "Exception Type",
    "severity": "Severity",
    "resolution_status": "Resolution Status",
    "detected_at": "Detected At",
    "event_id": "Event ID",
    "event_type": "Event Type",
    "event_city": "Event City",
    "event_state": "Event State",
    "event_timestamp": "Event Timestamp",
}


def field_label(key: str) -> str:
    """Return the user facing label for a known API field, or a generated fallback."""
    return FIELD_LABELS.get(key, str(key).replace("_", " ").title())


def call_api(path: str, params: dict[str, Any] | None = None) -> tuple[dict[str, Any] | list[dict[str, Any]] | None, str | None, int | None]:
    try:
        response = requests.get(
            f"{API_BASE_URL}{path}",
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return None, f"Backend request failed: {exc}", None

    if response.status_code >= 400:
        try:
            payload = response.json()
            detail = payload.get("detail", "Request failed.")
        except ValueError:
            detail = response.text or "Request failed."
        return None, detail, response.status_code

    try:
        return response.json(), None, response.status_code
    except ValueError:
        return None, "Backend returned a non-JSON response.", response.status_code


def call_api_post(
    path: str,
    payload: dict[str, Any],
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> tuple[dict[str, Any] | list[dict[str, Any]] | None, str | None, int | None]:
    try:
        response = requests.post(
            f"{API_BASE_URL}{path}",
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return None, f"Backend is unavailable. Please ensure the FastAPI server is running. Details: {exc}", None

    if response.status_code >= 400:
        try:
            body = response.json()
            detail = body.get("detail", "Request failed.")
        except ValueError:
            detail = response.text or "Request failed."
        return None, detail, response.status_code

    try:
        return response.json(), None, response.status_code
    except ValueError:
        return None, "Backend returned a non-JSON response.", response.status_code


def _field_value_rows(record: dict[str, Any] | None) -> list[dict[str, str]]:
    """Turn a flat dict into labeled Field/Value rows for a small reference table."""
    if not record:
        return []
    return [
        {"Field": field_label(key), "Value": str(value)} for key, value in record.items()
    ]


def _rename_to_labels(frame: pd.DataFrame) -> pd.DataFrame:
    """Rename a table's columns to their user facing labels."""
    if frame.empty:
        return frame
    return frame.rename(columns={column: field_label(column) for column in frame.columns})


SHIPMENT_SUMMARY_FIELDS = [
    "shipment_id",
    "customer_name",
    "customer_tier",
    "planned_delivery_date",
    "actual_delivery_date",
]


def shipment_summary_rows(shipment: dict[str, Any] | None) -> list[dict[str, str]]:
    """Return the shipment facts worth showing beyond the headline metrics."""
    if not shipment:
        return []
    return [
        {"Field": field_label(key), "Value": str(shipment.get(key, ""))}
        for key in SHIPMENT_SUMMARY_FIELDS
    ]


def carrier_context_rows(
    shipment: dict[str, Any] | None, graph_context: dict[str, Any] | None
) -> list[dict[str, str]]:
    """Return carrier reference rows, preferring graph context over the shipment record."""
    carrier = graph_context.get("carrier") if graph_context else None
    if carrier:
        return _field_value_rows(carrier)
    if shipment:
        return [
            {"Field": field_label("carrier_name"), "Value": str(shipment.get("carrier_name", ""))},
            {"Field": field_label("carrier_type"), "Value": str(shipment.get("carrier_type", ""))},
        ]
    return []


def route_context_rows(
    shipment: dict[str, Any] | None, graph_context: dict[str, Any] | None
) -> list[dict[str, str]]:
    """Return route reference rows, preferring graph context over the shipment record."""
    route = graph_context.get("route") if graph_context else None
    if route:
        return _field_value_rows(route)
    if shipment:
        origin = f"{shipment.get('origin_city', '')}, {shipment.get('origin_state', '')}"
        destination = f"{shipment.get('destination_city', '')}, {shipment.get('destination_state', '')}"
        return [
            {"Field": "Origin", "Value": origin},
            {"Field": "Destination", "Value": destination},
        ]
    return []


def exception_detail_rows(graph_context: dict[str, Any] | None) -> list[dict[str, str]]:
    """Return exception reference rows, or an empty list when there is no exception."""
    if not graph_context:
        return []
    return _field_value_rows(graph_context.get("exception"))


def events_dataframe(graph_context: dict[str, Any] | None) -> pd.DataFrame:
    """Return the ordered event table for a shipment, or an empty frame."""
    if not graph_context:
        return pd.DataFrame()
    events = graph_context.get("events") or []
    if not events:
        return pd.DataFrame()
    frame = pd.DataFrame(events)
    preferred_columns = ["event_timestamp", "event_type", "event_city", "event_state"]
    ordered_columns = [column for column in preferred_columns if column in frame.columns]
    remaining_columns = [column for column in frame.columns if column not in ordered_columns]
    frame = frame[ordered_columns + remaining_columns]
    return _rename_to_labels(frame)


def records_dataframe(records: list[dict[str, Any]] | None) -> pd.DataFrame:
    """Return a labeled table for a list of records (peer shipments or precedents)."""
    if not records:
        return pd.DataFrame()
    return _rename_to_labels(pd.DataFrame(records))


def sop_guidance_text(sop_guidance: dict[str, Any] | None) -> tuple[str, list[str]]:
    """Return (answer, sources) for the SOP guidance section, or ("", []) when unavailable."""
    if not sop_guidance:
        return "", []
    answer = str(sop_guidance.get("answer", "")).strip()
    sources = list(sop_guidance.get("sources") or [])
    return answer, sources


def retrieval_sources_label(retrieval_sources: list[str] | None) -> str:
    """Return a readable label listing which backends contributed to a response."""
    if not retrieval_sources:
        return "No retrieval sources reported."
    return ", ".join(retrieval_sources)


def render_sources(sources: Any) -> None:
    """Render response sources when the API returns them."""
    if isinstance(sources, list) and sources:
        st.subheader("Sources")
        for source in sources:
            st.write(f"- {source}")


def render_retrieved_evidence(data: Any) -> None:
    """Keep raw assistant evidence available without making it the default view."""
    with st.expander("Retrieved evidence", expanded=False):
        if isinstance(data, list):
            if data:
                st.dataframe(pd.DataFrame(data), width="stretch", hide_index=True)
            else:
                st.write("No data returned.")
        elif isinstance(data, dict):
            st.json(data)
        else:
            st.write("No data returned.")


def apply_page_style() -> None:
    """Keep presentation consistent while respecting the active Streamlit theme."""
    st.markdown(
        """
        <style>
        .block-container {max-width: 1280px; padding-top: 2.5rem; padding-bottom: 3rem;}
        h1, h2, h3 {letter-spacing: -0.025em;}
        [data-testid="stMetric"] {
            background: var(--secondary-background-color);
            border: 1px solid rgba(128,128,128,.2);
            border-radius: 12px; padding: 1rem 1.2rem;
        }
        [data-testid="stMetricValue"] {font-size: 1.65rem;}
        [data-testid="stSidebar"] {border-right: 1px solid rgba(128,128,128,.2);}
        </style>
        """,
        unsafe_allow_html=True,
    )


def navigate_to(page: str) -> None:
    st.session_state["navigation"] = page


def render_home() -> None:
    st.caption("FREIGHT VISIBILITY / OPERATIONS WORKSPACE")
    st.title("Every shipment. A clearer picture.")
    st.write(
        "Track freight, investigate delays, and find the guidance to take the next step."
    )
    st.caption("Portfolio demonstration • Synthetic shipment data • Local-first architecture")

    health_data, error, _ = call_api("/health")
    if error:
        st.error("The backend is unavailable. Start the FastAPI service to load shipment data.")
        with st.expander("Connection details"):
            st.write(error)
    elif isinstance(health_data, dict):
        if health_data.get("status") == "ok":
            st.success("Connected · Shipment services are ready.")
        else:
            st.warning("Connected, but the backend did not report a healthy status.")
        with st.expander("Service details"):
            st.json(health_data)

    st.subheader("Start with your next decision")
    cards = [
        ("Track a shipment", "Check status, delivery dates, and the latest shipment events.", "Shipment Lookup"),
        ("Investigate risk", "Review shipments flagged for delays, exceptions, or elevated risk.", "High-Risk Shipments"),
        ("Ask the assistant", "Explore shipment context and source-backed operating guidance.", "Assistant Chat"),
    ]
    for column, (title, description, destination) in zip(st.columns(3), cards):
        with column:
            with st.container(border=True):
                st.subheader(title)
                st.write(description)
                st.button("Open " + destination, key="open_" + destination,
                          width="stretch", on_click=navigate_to, args=(destination,))
    st.divider()
    st.subheader("Explore the demo")
    st.write("Start with **SHP-1001** in Shipment Lookup, then inspect its events or ask the assistant for context.")
    st.caption("Use Delay Analytics to compare carriers and lanes, or SOP Assistant to search operating procedures.")


def render_shipment_lookup() -> None:
    st.header("Shipment Lookup")
    st.caption("Delivery status and shipment details in one place.")
    shipment_id = st.text_input("Shipment ID", value="SHP-1001").strip()

    if not shipment_id:
        st.info("Enter a shipment ID to load details.")
        return

    shipment, error, status_code = call_api(f"/shipments/{shipment_id}")
    if error:
        if status_code == 404:
            st.warning(error)
        else:
            st.error(error)
        return

    if isinstance(shipment, dict):
        st.subheader("Shipment Summary")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Status", str(shipment.get("shipment_status", "")))
        col2.metric("Transport Mode", str(shipment.get("shipment_mode", "")))
        col3.metric("Delayed", "Yes" if shipment.get("is_delayed") else "No")
        col4.metric("Delay Days", int(shipment.get("delay_days", 0)))

        st.subheader("Shipment Details")
        st.dataframe(pd.DataFrame(_field_value_rows(shipment)), width="stretch", hide_index=True)


def render_shipment_events() -> None:
    st.header("Shipment Events")
    st.caption("Follow the recorded milestones for a shipment.")
    shipment_id = st.text_input("Shipment ID", value="SHP-1001", key="events_shipment_id").strip()

    if not shipment_id:
        st.info("Enter a shipment ID to load events.")
        return

    events, error, status_code = call_api(f"/shipments/{shipment_id}/events")
    if error:
        if status_code == 404:
            st.warning(error)
        else:
            st.error(error)
        return

    if isinstance(events, list):
        events_df = pd.DataFrame(events)
        if events_df.empty:
            st.info("No events found for this shipment.")
            return
        st.dataframe(_rename_to_labels(events_df), width="stretch", hide_index=True)


def render_delay_analytics() -> None:
    st.header("Delay Analytics")
    st.caption("Compare delay patterns across carriers and lanes.")
    data, error, _ = call_api("/analytics/delay-rates")
    if error:
        st.error(error)
        return

    if not isinstance(data, list):
        st.error("Unexpected response format.")
        return

    df = pd.DataFrame(data)
    if df.empty:
        st.info("No analytics data available.")
        return

    total = int(df["total_shipments"].sum())
    delayed = int(df["delayed_shipments"].sum())
    col1, col2, col3 = st.columns(3)
    col1.metric("Shipments analyzed", f"{total:,}")
    col2.metric("Delayed shipments", f"{delayed:,}")
    col3.metric("Overall delay rate", f"{delayed / total:.1%}" if total else "—")

    st.subheader("Top Delay Rates by Carrier")
    carrier_delay = (
        df.groupby("carrier_name", as_index=False)["delay_rate"]
        .mean()
        .sort_values("delay_rate", ascending=False)
        .head(10)
        .set_index("carrier_name")
    )
    st.caption("Mean delay rate across each carrier's lane groups; each group has equal weight.")
    st.bar_chart(carrier_delay.rename(columns={"delay_rate": "Delay rate"}))
    st.subheader("Carrier and lane breakdown")
    st.dataframe(_rename_to_labels(df), width="stretch", hide_index=True,
                 column_config={"Delay Rate": st.column_config.NumberColumn(format="percent")})


def highlight_risk_flags(row: pd.Series) -> list[str]:
    styles = [""] * len(row)
    columns = list(row.index)
    if bool(row.get("exception_flag", False)):
        if "exception_flag" in columns:
            styles[columns.index("exception_flag")] = "background-color: #fde68a"
    if bool(row.get("is_delayed", False)):
        if "is_delayed" in columns:
            styles[columns.index("is_delayed")] = "background-color: #fecaca"
        if "delay_days" in columns:
            styles[columns.index("delay_days")] = "background-color: #fecaca"
    return styles


def render_high_risk_shipments() -> None:
    st.header("High-Risk Shipments")
    st.caption("Prioritize shipments with delays, exceptions, or elevated carrier and route risk.")
    limit = st.number_input("Maximum shipments to show", min_value=1, max_value=500, value=50, step=1)
    data, error, _ = call_api("/analytics/high-risk-shipments", params={"limit": int(limit)})
    if error:
        st.error(error)
        return

    if not isinstance(data, list):
        st.error("Unexpected response format.")
        return

    df = pd.DataFrame(data)
    if df.empty:
        st.info("No high-risk shipments returned.")
        return

    st.caption(f"Showing {len(df):,} shipments · Red highlights delays; amber highlights exceptions.")
    styled = df.style.apply(highlight_risk_flags, axis=1).format(precision=2)
    styled = styled.relabel_index([field_label(c) for c in df.columns], axis=1)
    st.dataframe(styled, width="stretch", hide_index=True)


def render_sop_assistant() -> None:
    st.header("SOP Assistant")
    st.caption("Search operating procedures and review the supporting sources.")
    question = st.text_input(
        "Ask an SOP/FAQ question",
        value="What is the SOP for customs delay escalation?",
    ).strip()

    if not question:
        st.info("Enter a question to search SOP documents.")
        return

    result, error, _ = call_api_post("/assistant/sop-search", {"question": question})
    if error:
        st.error(error)
        return

    if not isinstance(result, dict):
        st.error("Unexpected response format.")
        return

    answer = str(result.get("answer", "")).strip()
    sources = result.get("sources", [])

    st.subheader("Answer")
    st.write(answer if answer else "No answer returned.")

    render_sources(sources)
    render_retrieved_evidence(result.get("data"))


def render_hybrid_response(result: dict[str, Any]) -> None:
    """Render a graph backed assistant response in clear, structured sections."""
    data = result.get("data")
    if not isinstance(data, dict):
        st.error("Unexpected response format.")
        return

    shipment = data.get("shipment")
    graph_context = data.get("graph_context")

    st.subheader("Shipment Summary")
    if shipment:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(field_label("shipment_status"), str(shipment.get("shipment_status", "")))
        col2.metric(field_label("shipment_mode"), str(shipment.get("shipment_mode", "")))
        col3.metric(field_label("is_delayed"), "Yes" if shipment.get("is_delayed") else "No")
        col4.metric(field_label("delay_days"), int(shipment.get("delay_days", 0)))
        st.dataframe(
            pd.DataFrame(shipment_summary_rows(shipment)), width="stretch", hide_index=True
        )
    else:
        st.info("No shipment data returned.")

    st.subheader("Carrier and Route Context")
    if graph_context is None and shipment:
        st.info(
            "Detailed graph context is currently unavailable. Showing carrier and "
            "route facts from the shipment record instead."
        )
    carrier_col, route_col = st.columns(2)
    with carrier_col:
        st.write("**Carrier**")
        carrier_rows = carrier_context_rows(shipment, graph_context)
        if carrier_rows:
            st.dataframe(pd.DataFrame(carrier_rows), width="stretch", hide_index=True)
        else:
            st.info("No carrier data available.")
    with route_col:
        st.write("**Route**")
        route_rows = route_context_rows(shipment, graph_context)
        if route_rows:
            st.dataframe(pd.DataFrame(route_rows), width="stretch", hide_index=True)
        else:
            st.info("No route data available.")

    st.subheader("Ordered Shipment Events")
    events_df = events_dataframe(graph_context)
    if events_df.empty:
        st.info("No event data available.")
    else:
        st.dataframe(events_df, width="stretch", hide_index=True)

    st.subheader("Exception Details")
    exception_rows = exception_detail_rows(graph_context)
    if exception_rows:
        st.dataframe(pd.DataFrame(exception_rows), width="stretch", hide_index=True)
    elif graph_context is None:
        st.info("Exception details are currently unavailable.")
    else:
        st.info("No exception recorded for this shipment.")

    st.subheader("Similar Shipments")
    peers_df = records_dataframe(data.get("peers"))
    if peers_df.empty:
        st.info("No similar shipments found.")
    else:
        st.dataframe(peers_df, width="stretch", hide_index=True)

    st.subheader("Previous Exception Outcomes")
    precedents_df = records_dataframe(data.get("precedents"))
    if precedents_df.empty:
        st.info("No previous exception outcomes found.")
    else:
        st.dataframe(precedents_df, width="stretch", hide_index=True)

    st.subheader("SOP Guidance")
    sop_answer, sop_sources = sop_guidance_text(data.get("sop_guidance"))
    if sop_answer:
        st.write(sop_answer)
        if sop_sources:
            st.write("**Sources**")
            for source in sop_sources:
                st.write(f"- {source}")
    else:
        st.info("No SOP guidance returned for this question.")

    st.subheader("Retrieval Sources")
    st.write(retrieval_sources_label(result.get("retrieval_sources")))
    render_retrieved_evidence(data)


def render_assistant_chat() -> None:
    st.header("Assistant Chat")
    st.caption("Ask about a shipment, delay patterns, or operating procedures. Include a shipment ID for shipment-specific questions.")
    question = st.text_input(
        "Ask a logistics question",
        value="Where is shipment SHP-1001?",
        key="assistant_chat_question",
    ).strip()

    if not question:
        st.info("Enter a question to continue.")
        return

    result, error, _ = call_api_post(
        "/assistant/chat",
        {"question": question},
        timeout=ASSISTANT_REQUEST_TIMEOUT_SECONDS,
    )
    if error:
        st.error(error)
        return

    if not isinstance(result, dict):
        st.error("Unexpected response format.")
        return

    route = str(result.get("route", "unknown"))
    answer = str(result.get("answer", "")).strip()

    with st.expander("How this answer was routed"):
        st.code(route)

    st.subheader("Answer")
    st.write(answer if answer else "No answer returned.")

    sources = result.get("sources", [])
    render_sources(sources)

    if route in HYBRID_ROUTES:
        render_hybrid_response(result)
        return

    data = result.get("data")
    render_retrieved_evidence(data)


def main() -> None:
    st.set_page_config(
        page_title="Freight Visibility AI Assistant",
        page_icon=":package:",
        layout="wide",
    )

    apply_page_style()
    st.sidebar.title("Freight Visibility")
    st.sidebar.caption("Shipment intelligence workspace")
    page = st.sidebar.radio(
        "Go to",
        [
            "Home",
            "Shipment Lookup",
            "Shipment Events",
            "Delay Analytics",
            "High-Risk Shipments",
            "SOP Assistant",
            "Assistant Chat",
        ],
        key="navigation",
    )
    st.sidebar.divider()
    st.sidebar.caption("DEMO ENVIRONMENT")
    st.sidebar.caption("Synthetic data · Local-first\n\nShipment tracking, risk analysis, and grounded guidance.")

    if page == "Home":
        render_home()
    elif page == "Shipment Lookup":
        render_shipment_lookup()
    elif page == "Shipment Events":
        render_shipment_events()
    elif page == "Delay Analytics":
        render_delay_analytics()
    elif page == "High-Risk Shipments":
        render_high_risk_shipments()
    elif page == "SOP Assistant":
        render_sop_assistant()
    else:
        render_assistant_chat()


if __name__ == "__main__":
    main()
