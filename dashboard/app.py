"""
Team B — dashboard/app.py
Streamlit dashboard consuming the FastAPI backend.
Run: streamlit run dashboard/app.py
Make sure the API is running at localhost:8000 first.
"""

import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

API_BASE = "http://localhost:8000"
REFRESH_INTERVAL = 30   # seconds

st.set_page_config(
    page_title="OPD Management",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── helpers ────────────────────────────────────────────────────────────────────

def api_get(path: str) -> dict:
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to API. Start the backend: uvicorn api.main:app --reload")
        return {}
    except Exception as e:
        st.error(f"API error: {e}")
        return {}


def api_post(path: str, payload: dict) -> dict:
    try:
        r = requests.post(f"{API_BASE}{path}", json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to API.")
        return {}
    except Exception as e:
        st.error(f"API error: {e}")
        return {}


# ── sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🏥 OPD System")
    st.caption("Outpatient Department Management")
    st.divider()

    page = st.radio(
        "Navigation",
        ["Dashboard", "Triage", "Schedule", "Analytics"],
        label_visibility="collapsed",
    )

    st.divider()
    health = api_get("/health")
    if health:
        st.caption("System status")
        st.write("✅ API online" if health else "❌ API offline")
        st.write("✅ Wait model" if health.get("wait_model_loaded") else "⚠️ Wait model missing")
        st.write("✅ Triage model" if health.get("triage_model_loaded") else "⚠️ Triage model missing")
        st.write("✅ Database" if health.get("db_exists") else "⚠️ No database")

    if st.button("↻ Refresh", use_container_width=True):
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

if page == "Dashboard":
    st.title("OPD Real-time Dashboard")
    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    # ── header metric cards ──────────────────────────────────────────────────
    stats = api_get("/stats")
    queue = api_get("/queue")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Queue length",       queue.get("queue_length", "–"))
    with col2:
        st.metric("In service",         queue.get("in_service_count", "–"))
    with col3:
        st.metric("Avg wait today",
                  f"{queue.get('avg_wait_min', '–')} min")
    with col4:
        st.metric("No-shows today",     queue.get("no_shows", "–"))

    st.divider()

    # ── appointments table ───────────────────────────────────────────────────
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("Today's appointments")
        appts = queue.get("appointments", [])
        if appts:
            df = pd.DataFrame(appts)
            display_cols = [c for c in
                ["appt_id", "patient_id", "service_type", "doctor_id",
                 "arrival_time", "wait_minutes", "no_show"]
                if c in df.columns]
            st.dataframe(df[display_cols], use_container_width=True, height=340)
        else:
            st.info("No appointments found. Generate data first.")

    with col_right:
        st.subheader("Queue by service")
        if appts:
            df = pd.DataFrame(appts)
            if "service_type" in df.columns:
                svc_counts = df["service_type"].value_counts().reset_index()
                svc_counts.columns = ["service", "count"]
                fig = px.bar(svc_counts, x="count", y="service",
                             orientation="h", color="service",
                             color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_layout(showlegend=False, height=340,
                                  margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available.")

    # ── wait time by hour ────────────────────────────────────────────────────
    st.subheader("Wait time by hour of day")
    if appts:
        df = pd.DataFrame(appts)
        if "hour_of_day" in df.columns and "wait_minutes" in df.columns:
            hourly = df.groupby("hour_of_day")["wait_minutes"].mean().reset_index()
            fig2 = px.line(hourly, x="hour_of_day", y="wait_minutes",
                           markers=True, labels={"hour_of_day": "Hour", "wait_minutes": "Avg wait (min)"})
            fig2.update_layout(height=260, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig2, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — TRIAGE
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Triage":
    st.title("Patient Triage")
    st.caption("Enter vital signs to get urgency classification and wait estimate.")

    col_form, col_result = st.columns([1, 1])

    with col_form:
        st.subheader("Vital signs input")

        bp  = st.slider("Blood pressure (systolic mmHg)", 70, 200, 120)
        hr  = st.slider("Heart rate (bpm)", 40, 160, 75)
        tmp = st.slider("Temperature (°C)", 35.0, 41.0, 37.0, step=0.1)
        pain = st.slider("Pain score (0–10)", 0, 10, 3)

        st.divider()
        st.subheader("Wait time estimate")
        svc = st.selectbox(
            "Service type",
            ["general", "cardiology", "orthopedic", "pediatrics", "neurology"]
        )
        hour = st.slider("Arrival hour", 7, 18, datetime.now().hour)
        dow  = st.selectbox("Day", ["Mon", "Tue", "Wed", "Thu", "Fri"],
                            index=min(datetime.now().weekday(), 4))
        dow_map = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4}
        queue_len = st.number_input("Current queue length", 0, 50, 5)

        run = st.button("Run assessment", type="primary", use_container_width=True)

    with col_result:
        st.subheader("Assessment result")

        if run:
            with st.spinner("Classifying …"):
                triage_res = api_post("/triage", {
                    "bp_systolic": bp,
                    "heart_rate":  hr,
                    "temp_c":      tmp,
                    "pain_score":  pain,
                })
                wait_res = api_post("/forecast", {
                    "service_type": svc,
                    "hour_of_day":  hour,
                    "day_of_week":  dow_map[dow],
                    "queue_length": queue_len,
                })

            if triage_res:
                level = triage_res.get("urgency_level", "unknown")
                conf  = triage_res.get("confidence_pct", 0)
                color = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(level, "⚪")

                st.markdown(f"### {color} Urgency: **{level.upper()}**")
                st.caption(f"Confidence: {conf}%")

                probs = triage_res.get("probabilities", {})
                if probs:
                    prob_df = pd.DataFrame(
                        list(probs.items()), columns=["Level", "Probability %"]
                    )
                    fig = px.bar(prob_df, x="Level", y="Probability %",
                                 color="Level",
                                 color_discrete_map={
                                     "high": "#ef4444",
                                     "medium": "#f59e0b",
                                     "low": "#22c55e",
                                 })
                    fig.update_layout(showlegend=False, height=220,
                                      margin=dict(l=0, r=0, t=0, b=0))
                    st.plotly_chart(fig, use_container_width=True)

            if wait_res:
                wait_min = wait_res.get("predicted_wait_min", "–")
                st.metric("Predicted wait time", f"{wait_min} min")
        else:
            st.info("Fill in the form and click 'Run assessment'.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — SCHEDULE
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Schedule":
    st.title("Schedule Optimizer")
    st.caption("Add patients and generate an optimized appointment schedule.")

    if "patients" not in st.session_state:
        st.session_state.patients = []

    col_add, col_list = st.columns([1, 2])

    with col_add:
        st.subheader("Add patient")
        pid    = st.text_input("Patient ID", f"P{len(st.session_state.patients)+1:04d}")
        arr    = st.time_input("Arrival time", datetime.now().replace(second=0, microsecond=0))
        svc2   = st.selectbox("Service", ["general","cardiology","orthopedic","pediatrics","neurology"], key="svc2")
        prio   = st.select_slider("Priority", options=[1, 2, 3],
                                  format_func=lambda x: {1:"Low",2:"Medium",3:"High"}[x])
        dur    = st.number_input("Duration (min)", 5, 60, 15)

        if st.button("Add to queue", use_container_width=True):
            today_str = datetime.now().strftime("%Y-%m-%d")
            st.session_state.patients.append({
                "patient_id":   pid,
                "arrival_time": f"{today_str}T{arr.strftime('%H:%M:%S')}",
                "service_type": svc2,
                "priority":     prio,
                "duration_min": dur,
            })
            st.success(f"Added {pid}")

        if st.button("Clear all", use_container_width=True):
            st.session_state.patients = []

    with col_list:
        st.subheader(f"Queue ({len(st.session_state.patients)} patients)")
        if st.session_state.patients:
            st.dataframe(pd.DataFrame(st.session_state.patients),
                         use_container_width=True, height=250)

            if st.button("▶ Optimize schedule", type="primary", use_container_width=True):
                with st.spinner("Optimizing …"):
                    result = api_post("/schedule", {"patients": st.session_state.patients})

                if result and "assignments" in result:
                    st.success(
                        f"Scheduled {result['total_patients']} patients | "
                        f"Avg wait: {result['avg_wait_min']} min"
                    )
                    df_sched = pd.DataFrame(result["assignments"])
                    st.dataframe(df_sched, use_container_width=True)

                    # Gantt chart
                    df_sched["start_time"] = pd.to_datetime(df_sched["start_time"])
                    df_sched["end_time"]   = pd.to_datetime(df_sched["end_time"])
                    fig = px.timeline(
                        df_sched,
                        x_start="start_time", x_end="end_time",
                        y="doctor_id", color="patient_id",
                        title="Doctor schedule (Gantt)",
                    )
                    fig.update_yaxes(autorange="reversed")
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Add patients using the form on the left.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Analytics":
    st.title("Analytics")

    queue = api_get("/queue")
    appts = queue.get("appointments", [])

    if not appts:
        st.info("No data available. Run data_generator.py first.")
    else:
        df = pd.DataFrame(appts)

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Wait time distribution")
            if "wait_minutes" in df.columns:
                fig = px.histogram(df, x="wait_minutes", nbins=20,
                                   labels={"wait_minutes": "Wait (min)"},
                                   color_discrete_sequence=["#6366f1"])
                fig.update_layout(height=280, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("No-show rate by service")
            if "service_type" in df.columns and "no_show" in df.columns:
                ns = df.groupby("service_type")["no_show"].mean().mul(100).reset_index()
                ns.columns = ["service", "no_show_rate"]
                fig2 = px.bar(ns, x="service", y="no_show_rate",
                              labels={"no_show_rate": "No-show %"},
                              color_discrete_sequence=["#f59e0b"])
                fig2.update_layout(height=280, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Arrivals by hour")
        if "hour_of_day" in df.columns:
            hourly_cnt = df.groupby("hour_of_day").size().reset_index(name="arrivals")
            fig3 = px.bar(hourly_cnt, x="hour_of_day", y="arrivals",
                          labels={"hour_of_day": "Hour of day"},
                          color_discrete_sequence=["#22c55e"])
            fig3.update_layout(height=260, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig3, use_container_width=True)
