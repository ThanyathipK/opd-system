"""
Team A — api/main.py
FastAPI backend exposing /triage, /forecast, /schedule, /queue endpoints.
Run: uvicorn api.main:app --reload --port 8000
"""

import pickle
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text

# ── paths ──────────────────────────────────────────────────────────────────────
BASE    = Path(__file__).parent.parent
DB_PATH = BASE / "opd.db"
PKL_DIR = BASE / "models"

app = FastAPI(title="OPD Management API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── load models at startup ─────────────────────────────────────────────────────
_wait_bundle   = None
_triage_bundle = None

def get_engine():
    return create_engine(f"sqlite:///{DB_PATH}")

@app.on_event("startup")
def load_models():
    global _wait_bundle, _triage_bundle
    wait_path   = PKL_DIR / "wait_time.pkl"
    triage_path = PKL_DIR / "triage.pkl"

    if wait_path.exists():
        with open(wait_path, "rb") as f:
            _wait_bundle = pickle.load(f)
        print("✓ wait_time.pkl loaded")
    else:
        print("⚠ wait_time.pkl not found — run models/train.py first")

    if triage_path.exists():
        with open(triage_path, "rb") as f:
            _triage_bundle = pickle.load(f)
        print("✓ triage.pkl loaded")
    else:
        print("⚠ triage.pkl not found — run models/train.py first")


# ── schemas ────────────────────────────────────────────────────────────────────

class TriageInput(BaseModel):
    bp_systolic: float
    heart_rate:  float
    temp_c:      float
    pain_score:  int            # 0–10

class ForecastInput(BaseModel):
    service_type: str           # general / cardiology / …
    hour_of_day:  int           # 0–23
    day_of_week:  int           # 0=Mon … 6=Sun
    queue_length: int

class SchedulePatient(BaseModel):
    patient_id:   str
    arrival_time: str           # ISO format "2024-01-15T09:30:00"
    service_type: str
    priority:     int = 1       # 1=low 2=med 3=high
    duration_min: int = 15

class ScheduleRequest(BaseModel):
    patients: List[SchedulePatient]
    date:     Optional[str] = None


# ── endpoints ──────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "OPD API running", "docs": "/docs"}


@app.get("/health")
def health():
    return {
        "wait_model_loaded":   _wait_bundle   is not None,
        "triage_model_loaded": _triage_bundle is not None,
        "db_exists":           DB_PATH.exists(),
    }


@app.post("/triage")
def predict_triage(data: TriageInput):
    """
    Returns urgency level (low / medium / high) from vital signs.
    Team B calls this from the triage form in the dashboard.
    """
    if _triage_bundle is None:
        raise HTTPException(503, "Triage model not loaded. Run models/train.py first.")

    model = _triage_bundle["model"]
    le    = _triage_bundle["label_encoder"]
    feats = _triage_bundle["features"]

    X = pd.DataFrame([{
        "bp_systolic": data.bp_systolic,
        "heart_rate":  data.heart_rate,
        "temp_c":      data.temp_c,
        "pain_score":  data.pain_score,
    }])[feats]

    pred_idx  = model.predict(X)[0]
    pred_prob = model.predict_proba(X)[0]
    label     = le.inverse_transform([pred_idx])[0]
    confidence = round(float(pred_prob.max()) * 100, 1)

    return {
        "urgency_level": label,
        "confidence_pct": confidence,
        "probabilities": dict(zip(le.classes_, [round(p*100,1) for p in pred_prob])),
    }


@app.post("/forecast")
def predict_wait(data: ForecastInput):
    """
    Returns predicted wait time in minutes.
    Team B calls this when a patient checks in.
    """
    if _wait_bundle is None:
        raise HTTPException(503, "Wait-time model not loaded. Run models/train.py first.")

    model = _wait_bundle["model"]
    le    = _wait_bundle["label_encoder"]
    feats = _wait_bundle["features"]

    try:
        svc_enc = le.transform([data.service_type])[0]
    except ValueError:
        raise HTTPException(400, f"Unknown service_type '{data.service_type}'. "
                                 f"Valid: {list(le.classes_)}")

    X = pd.DataFrame([{
        "hour_of_day":  data.hour_of_day,
        "day_of_week":  data.day_of_week,
        "queue_length": data.queue_length,
        "service_enc":  svc_enc,
    }])[feats]

    wait = float(model.predict(X)[0])
    return {
        "predicted_wait_min": round(max(0, wait), 1),
        "service_type":       data.service_type,
        "queue_length":       data.queue_length,
    }


@app.post("/schedule")
def get_schedule(req: ScheduleRequest):
    """
    Returns optimized appointment schedule.
    Team B renders this as the schedule grid in the dashboard.
    """
    import sys
    sys.path.insert(0, str(BASE))
    from optimizer.scheduler import Patient, Doctor, optimize_schedule

    engine = get_engine()
    doctors_df = pd.read_sql("SELECT * FROM staff", engine)

    now = datetime.now()
    doctors = [
        Doctor(
            doctor_id      = row["doctor_id"],
            name           = row["name"],
            specialization = row["specialization"],
            available_from = now,
        )
        for _, row in doctors_df.iterrows()
    ]

    patients = [
        Patient(
            patient_id   = p.patient_id,
            arrival_time = datetime.fromisoformat(p.arrival_time),
            service_type = p.service_type,
            priority     = p.priority,
            duration_min = p.duration_min,
        )
        for p in req.patients
    ]

    assignments = optimize_schedule(patients, doctors)

    return {
        "assignments": [
            {
                "patient_id":   a.patient_id,
                "doctor_id":    a.doctor_id,
                "start_time":   a.start_time.isoformat(),
                "end_time":     a.end_time.isoformat(),
                "wait_minutes": round(a.wait_minutes, 1),
            }
            for a in assignments
        ],
        "total_patients": len(assignments),
        "avg_wait_min":   round(
            sum(a.wait_minutes for a in assignments) / max(1, len(assignments)), 1
        ),
    }


@app.get("/queue")
def get_queue():
    """
    Returns today's live queue state from the DB.
    Team B polls this every 30s to refresh the dashboard.
    """
    if not DB_PATH.exists():
        raise HTTPException(503, "Database not found. Run data/data_generator.py first.")

    engine = get_engine()
    today  = datetime.now().strftime("%Y-%m-%d")

    appts = pd.read_sql(
        f"SELECT * FROM appointments WHERE DATE(arrival_time) = '{today}'",
        engine
    )

    if appts.empty:
        # fallback: return last day in DB for demo purposes
        appts = pd.read_sql(
            "SELECT * FROM appointments ORDER BY arrival_time DESC LIMIT 30",
            engine
        )

    waiting   = appts[appts["actual_start"].isna() & (appts["no_show"] == 0)]
    in_service = appts[appts["actual_start"].notna() & appts["actual_end"].isna()]

    return {
        "queue_length":      len(waiting),
        "in_service_count":  len(in_service),
        "total_today":       len(appts),
        "no_shows":          int(appts["no_show"].sum()),
        "avg_wait_min":      round(appts["wait_minutes"].mean(), 1)
                             if "wait_minutes" in appts.columns else None,
        "appointments":      appts.head(50).to_dict(orient="records"),
    }


@app.get("/doctors")
def get_doctors():
    engine = get_engine()
    df = pd.read_sql("SELECT * FROM staff", engine)
    return df.to_dict(orient="records")


@app.get("/stats")
def get_stats():
    """Summary stats for the dashboard header cards."""
    engine = get_engine()
    appts  = pd.read_sql("SELECT * FROM appointments", engine)

    return {
        "total_appointments": len(appts),
        "avg_wait_min":       round(appts["wait_minutes"].mean(), 1)
                              if "wait_minutes" in appts.columns else 0,
        "no_show_rate_pct":   round(appts["no_show"].mean() * 100, 1),
        "busiest_hour":       int(appts["hour_of_day"].mode()[0])
                              if "hour_of_day" in appts.columns else 9,
    }
