"""
Team C — tests/test_api.py
Automated tests for all API endpoints.
Run: pytest tests/ -v
Requires: API running OR use TestClient (no server needed).
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from api.main import app

client = TestClient(app)


# ── health ─────────────────────────────────────────────────────────────────────

def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "OPD API running" in r.json()["status"]


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "wait_model_loaded" in data
    assert "triage_model_loaded" in data
    assert "db_exists" in data


# ── triage ─────────────────────────────────────────────────────────────────────

TRIAGE_PAYLOAD = {
    "bp_systolic": 140,
    "heart_rate": 95,
    "temp_c": 38.2,
    "pain_score": 7,
}

def test_triage_valid():
    r = client.post("/triage", json=TRIAGE_PAYLOAD)
    # 200 if model loaded, 503 if not trained yet — both are acceptable
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        data = r.json()
        assert data["urgency_level"] in ("low", "medium", "high")
        assert 0 <= data["confidence_pct"] <= 100
        assert "probabilities" in data


def test_triage_normal_vitals():
    r = client.post("/triage", json={
        "bp_systolic": 115, "heart_rate": 70, "temp_c": 36.8, "pain_score": 1
    })
    assert r.status_code in (200, 503)


def test_triage_missing_field():
    r = client.post("/triage", json={"bp_systolic": 120})
    assert r.status_code == 422   # validation error


# ── forecast ───────────────────────────────────────────────────────────────────

FORECAST_PAYLOAD = {
    "service_type": "general",
    "hour_of_day": 9,
    "day_of_week": 0,
    "queue_length": 8,
}

def test_forecast_valid():
    r = client.post("/forecast", json=FORECAST_PAYLOAD)
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        data = r.json()
        assert data["predicted_wait_min"] >= 0
        assert data["service_type"] == "general"


def test_forecast_invalid_service():
    r = client.post("/forecast", json={
        **FORECAST_PAYLOAD, "service_type": "dentistry"
    })
    # 400 bad request if model loaded, 503 if not
    assert r.status_code in (400, 503)


def test_forecast_peak_hour():
    r = client.post("/forecast", json={**FORECAST_PAYLOAD, "hour_of_day": 9, "queue_length": 15})
    assert r.status_code in (200, 503)


# ── schedule ───────────────────────────────────────────────────────────────────

SCHEDULE_PAYLOAD = {
    "patients": [
        {
            "patient_id": "P0001",
            "arrival_time": "2024-01-15T09:00:00",
            "service_type": "general",
            "priority": 2,
            "duration_min": 15,
        },
        {
            "patient_id": "P0002",
            "arrival_time": "2024-01-15T09:10:00",
            "service_type": "cardiology",
            "priority": 3,
            "duration_min": 20,
        },
        {
            "patient_id": "P0003",
            "arrival_time": "2024-01-15T09:05:00",
            "service_type": "general",
            "priority": 1,
            "duration_min": 12,
        },
    ]
}

def test_schedule_returns_assignments():
    r = client.post("/schedule", json=SCHEDULE_PAYLOAD)
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        data = r.json()
        assert "assignments" in data
        assert data["total_patients"] == len(SCHEDULE_PAYLOAD["patients"])
        assert data["avg_wait_min"] >= 0
        for a in data["assignments"]:
            assert "patient_id" in a
            assert "doctor_id" in a
            assert "wait_minutes" in a


def test_schedule_empty():
    r = client.post("/schedule", json={"patients": []})
    assert r.status_code in (200, 503)


def test_schedule_high_priority_first():
    """High-priority patient should get earlier slot than low-priority."""
    r = client.post("/schedule", json=SCHEDULE_PAYLOAD)
    if r.status_code == 200:
        assignments = r.json()["assignments"]
        by_patient = {a["patient_id"]: a for a in assignments}
        # P0002 (priority=3) should start before or at same time as P0003 (priority=1)
        if "P0002" in by_patient and "P0003" in by_patient:
            assert by_patient["P0002"]["start_time"] <= by_patient["P0003"]["start_time"]


# ── queue & stats ──────────────────────────────────────────────────────────────

def test_queue_endpoint():
    r = client.get("/queue")
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        data = r.json()
        assert "queue_length" in data
        assert "appointments" in data


def test_stats_endpoint():
    r = client.get("/stats")
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        data = r.json()
        assert "total_appointments" in data
        assert "avg_wait_min" in data
        assert "no_show_rate_pct" in data


def test_doctors_endpoint():
    r = client.get("/doctors")
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert isinstance(r.json(), list)
