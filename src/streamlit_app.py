import streamlit as st
import pandas as pd
from src.database import db, TABLE_NAME
from src.anomaly_detector import anomaly_detector
from src.query_service import query_service
from src.llm_engine import llm_engine

st.set_page_config(
    page_title="DOTMappers Support AI Intelligence",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Support Ticket AI Intelligence System")
st.caption("DOTMappers AI Engineer Technical Assessment Sprint | End-to-End System")

# Sidebar
with st.sidebar:
    st.header("⚙️ System Status")
    stats = db.get_stats()
    st.metric("Total Records", stats["total_tickets"])
    st.metric("Open Tickets", stats["open_tickets"])
    st.metric("Avg Rating", f"{stats['avg_customer_rating']} ★")
    st.metric("Avg Resolution", f"{stats['avg_resolution_time_hrs']} hrs")
    
    st.divider()
    st.markdown(f"**Active LLM:** `{llm_engine.get_provider_name()}`")
    st.markdown("**API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)")

# Main Tabs
tab1, tab2, tab3 = st.tabs(["💬 Natural Language Query", "⚠️ Anomaly Detection", "📋 Dataset Explorer"])

# Tab 1: NL Query
with tab1:
    st.subheader("Natural Language Question Answering (Text-to-SQL)")
    st.write("Ask business or operational questions about customer support tickets:")
    
    col1, col2, col3 = st.columns(3)
    sample_choice = None
    with col1:
        if st.button("How many tickets are currently open?"):
            sample_choice = "How many tickets are currently open?"
        if st.button("Show me all Critical tickets not resolved within 12 hours."):
            sample_choice = "Show me all Critical tickets not resolved within 12 hours."
    with col2:
        if st.button("Which agent resolved the most tickets this month?"):
            sample_choice = "Which agent resolved the most tickets this month?"
        if st.button("What is the average customer rating for Technical category tickets?"):
            sample_choice = "What is the average customer rating for Technical category tickets?"
    with col3:
        if st.button("Are there any anomalies in resolution times this week?"):
            sample_choice = "Are there any anomalies in resolution times this week?"
        if st.button("Which agent has the lowest average customer rating?"):
            sample_choice = "Which agent has the lowest average customer rating?"

    user_query = st.text_input(
        "Enter query:", 
        value=sample_choice or "Which agent resolved the most tickets this month?"
    )

    if st.button("Run AI Query", type="primary"):
        if user_query:
            with st.spinner("Translating question to SQL and executing..."):
                response = query_service.execute_nl_query(user_query)

            if response.success:
                st.success(f"**AI Summary:** {response.summary}")
                st.info(f"⚡ Execution time: {response.execution_time_ms} ms | Provider: {response.provider}")
                
                with st.expander("🔍 Generated SQLite Query", expanded=True):
                    st.code(response.sql, language="sql")
                
                if response.results:
                    st.dataframe(pd.DataFrame(response.results), use_container_width=True)
                else:
                    st.warning("No rows returned.")
            else:
                st.error(f"Error: {response.error_message}")

# Tab 2: Anomalies
with tab2:
    st.subheader("Operational Anomaly Detection")
    col_a, col_b = st.columns(2)
    with col_a:
        sev_filter = st.selectbox("Filter by Severity:", ["All", "CRITICAL", "HIGH", "MEDIUM"])
    with col_b:
        type_filter = st.selectbox("Filter by Anomaly Type:", [
            "All", 
            "RESOLUTION_TIME_OUTLIER", 
            "UNRESOLVED_URGENT_TICKET", 
            "EXCESSIVE_FIRST_RESPONSE_TIME", 
            "LOW_CUSTOMER_SATISFACTION"
        ])

    anom_summary = anomaly_detector.detect_all_anomalies(
        severity_filter=None if sev_filter == "All" else sev_filter,
        anomaly_type_filter=None if type_filter == "All" else type_filter,
        limit=100
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Anomalies (Filtered)", anom_summary.total_anomalies)
    c2.metric("Critical Severities", anom_summary.by_severity.get("CRITICAL", 0))
    c3.metric("High Severities", anom_summary.by_severity.get("HIGH", 0))

    if anom_summary.anomalies:
        data = [a.model_dump() for a in anom_summary.anomalies]
        st.dataframe(pd.DataFrame(data), use_container_width=True)
    else:
        st.info("No anomalies detected for the selected criteria.")

# Tab 3: Raw Dataset
with tab3:
    st.subheader("Ingested Support Tickets")
    with db.get_connection() as conn:
        df_all = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME} ORDER BY created_at DESC", conn)
    st.dataframe(df_all, use_container_width=True)
