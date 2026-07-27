from __future__ import annotations

from typing import Any

import pandas as pd
import requests
import streamlit as st


API_BASE_URL = "http://127.0.0.1:8000"
REQUEST_TIMEOUT_SECONDS = 10


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


def call_api_post(path: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | list[dict[str, Any]] | None, str | None, int | None]:
    try:
        response = requests.post(
            f"{API_BASE_URL}{path}",
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
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


def render_home() -> None:
    st.title("Freight Visibility AI Assistant")
    st.write(
        "Local-first visibility for shipment tracking, delay monitoring, and risk detection "
        "across carriers, lanes, and customers."
    )

    health_data, error, _ = call_api("/health")
    st.subheader("Backend Status")
    if error:
        st.error(error)
        return

    if isinstance(health_data, dict):
        if health_data.get("status") == "ok":
            st.success(f"{health_data.get('service', 'service')} is healthy.")
        else:
            st.warning("Backend responded but did not report healthy status.")
        st.json(health_data)


def render_shipment_lookup() -> None:
    st.header("Shipment Lookup")
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
        col2.metric("Mode", str(shipment.get("shipment_mode", "")))
        col3.metric("Delayed", "Yes" if shipment.get("is_delayed") else "No")
        col4.metric("Delay Days", int(shipment.get("delay_days", 0)))

        st.subheader("Shipment Details")
        st.dataframe(pd.DataFrame([shipment]), width="stretch", hide_index=True)


def render_shipment_events() -> None:
    st.header("Shipment Events")
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
        st.dataframe(events_df, width="stretch", hide_index=True)


def render_delay_analytics() -> None:
    st.header("Delay Analytics")
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

    st.dataframe(df, width="stretch", hide_index=True)

    st.subheader("Top Delay Rates by Carrier")
    carrier_delay = (
        df.groupby("carrier_name", as_index=False)["delay_rate"]
        .mean()
        .sort_values("delay_rate", ascending=False)
        .head(10)
        .set_index("carrier_name")
    )
    st.bar_chart(carrier_delay)


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
    limit = st.number_input("Limit", min_value=1, max_value=500, value=50, step=1)
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

    styled = df.style.apply(highlight_risk_flags, axis=1)
    st.dataframe(styled, width="stretch", hide_index=True)


def render_sop_assistant() -> None:
    st.header("SOP Assistant")
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

    st.subheader("Sources")
    if isinstance(sources, list) and sources:
        for source in sources:
            st.write(f"- {source}")
    else:
        st.write("No sources returned.")


def render_assistant_chat() -> None:
    st.header("Assistant Chat")
    question = st.text_input(
        "Ask a logistics question",
        value="Where is shipment SHP-1001?",
        key="assistant_chat_question",
    ).strip()

    if not question:
        st.info("Enter a question to continue.")
        return

    result, error, _ = call_api_post("/assistant/chat", {"question": question})
    if error:
        st.error(error)
        return

    if not isinstance(result, dict):
        st.error("Unexpected response format.")
        return

    route = str(result.get("route", "unknown"))
    answer = str(result.get("answer", "")).strip()
    data = result.get("data")
    sources = result.get("sources", [])

    st.subheader("Route")
    st.code(route)

    st.subheader("Answer")
    st.write(answer if answer else "No answer returned.")

    st.subheader("Data")
    if isinstance(data, list):
        if data:
            st.dataframe(pd.DataFrame(data), width="stretch", hide_index=True)
        else:
            st.write("No data returned.")
    elif isinstance(data, dict):
        st.dataframe(pd.DataFrame([data]), width="stretch", hide_index=True)
    else:
        st.write("No data returned.")

    st.subheader("Sources")
    if isinstance(sources, list) and sources:
        for source in sources:
            st.write(f"- {source}")
    else:
        st.write("No sources returned.")


def main() -> None:
    st.set_page_config(
        page_title="Freight Visibility AI Assistant",
        page_icon=":package:",
        layout="wide",
    )

    st.sidebar.title("Navigation")
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
    )

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
