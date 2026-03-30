"""
Team A — data_generator.py
Generates synthetic OPD data and saves to SQLite via SQLAlchemy.
Run: python data/data_generator.py
"""

import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

# ── config ────────────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

DB_PATH = Path(__file__).parent.parent / "opd.db"
N_PATIENTS = 200
N_DAYS = 30
PEAK_HOURS = [8, 9, 10, 14, 15]   # arrival spikes

SERVICE_TYPES = {
    "general":     {"duration_min": 12, "std": 4},
    "cardiology":  {"duration_min": 20, "std": 6},
    "orthopedic":  {"duration_min": 18, "std": 5},
    "pediatrics":  {"duration_min": 10, "std": 3},
    "neurology":   {"duration_min": 25, "std": 7},
}

DOCTORS = [
    {"doctor_id": f"D{i:02d}", "name": f"Dr. Staff {i}",
     "specialization": spec}
    for i, spec in enumerate(
        ["general", "cardiology", "orthopedic", "pediatrics", "neurology"], 1
    )
]

ROOMS = [
    {"room_id": f"R{i:02d}", "room_type": t}
    for i, t in enumerate(
        ["consultation", "consultation", "procedure",
         "consultation", "observation"], 1
    )
]


# ── generators ────────────────────────────────────────────────────────────────

def gen_patients(n: int) -> pd.DataFrame:
    return pd.DataFrame({
        "patient_id": [f"P{i:04d}" for i in range(1, n + 1)],
        "age":        np.random.randint(1, 90, n),
        "gender":     np.random.choice(["M", "F"], n),
        "acuity":     np.random.choice(["low", "medium", "high"],
                                        n, p=[0.5, 0.35, 0.15]),
    })


def _random_arrival(day: datetime) -> datetime:
    """Bias arrivals toward peak hours."""
    if random.random() < 0.6:
        hour = random.choice(PEAK_HOURS)
    else:
        hour = random.randint(7, 17)
    minute = random.randint(0, 59)
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def gen_appointments(patients: pd.DataFrame, n_days: int) -> pd.DataFrame:
    rows = []
    appt_id = 1
    base_date = datetime(2024, 1, 1)

    for day_offset in range(n_days):
        day = base_date + timedelta(days=day_offset)
        if day.weekday() >= 5:          # skip weekends
            continue

        daily_count = np.random.randint(20, 40)
        sample_pts = patients.sample(daily_count, replace=True)

        for _, pt in sample_pts.iterrows():
            svc = random.choice(list(SERVICE_TYPES.keys()))
            doctor = random.choice(DOCTORS)
            room = random.choice(ROOMS)
            arrival = _random_arrival(day)
            sched_start = arrival + timedelta(minutes=random.randint(5, 30))
            duration = max(
                5,
                int(np.random.normal(
                    SERVICE_TYPES[svc]["duration_min"],
                    SERVICE_TYPES[svc]["std"],
                ))
            )
            sched_end = sched_start + timedelta(minutes=duration)
            delay = int(np.random.exponential(8))      # realistic delay
            actual_start = sched_start + timedelta(minutes=delay)
            actual_end = actual_start + timedelta(minutes=duration)
            no_show = int(random.random() < 0.08)

            rows.append({
                "appt_id":       f"A{appt_id:05d}",
                "patient_id":    pt["patient_id"],
                "arrival_time":  arrival,
                "service_type":  svc,
                "doctor_id":     doctor["doctor_id"],
                "room_id":       room["room_id"],
                "scheduled_start": sched_start,
                "scheduled_end":   sched_end,
                "actual_start":  actual_start if not no_show else None,
                "actual_end":    actual_end   if not no_show else None,
                "no_show":       no_show,
                "wait_minutes":  delay,
                "queue_length":  random.randint(1, 15),
                "hour_of_day":   arrival.hour,
                "day_of_week":   arrival.weekday(),
            })
            appt_id += 1

    return pd.DataFrame(rows)


def gen_triage(appointments: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, appt in appointments.iterrows():
        level = random.choices(
            ["low", "medium", "high"], weights=[50, 35, 15]
        )[0]
        rows.append({
            "triage_id":    f"T{_:05d}",
            "appt_id":      appt["appt_id"],
            "triage_level": level,
            "triage_notes": f"Routine {level} urgency assessment.",
            "bp_systolic":  int(np.random.normal(120, 15)),
            "heart_rate":   int(np.random.normal(75, 12)),
            "temp_c":       round(np.random.normal(37.0, 0.5), 1),
            "pain_score":   random.randint(0, 10),
        })
    return pd.DataFrame(rows)


# ── save to SQLite ─────────────────────────────────────────────────────────────

def save_to_db(patients, appointments, triage):
    engine = create_engine(f"sqlite:///{DB_PATH}")

    pd.DataFrame(SERVICE_TYPES).T.reset_index().rename(
        columns={"index": "service_type"}
    ).to_sql("services", engine, if_exists="replace", index=False)

    pd.DataFrame(DOCTORS).to_sql(
        "staff", engine, if_exists="replace", index=False
    )
    pd.DataFrame(ROOMS).to_sql(
        "rooms", engine, if_exists="replace", index=False
    )
    patients.to_sql("patients", engine, if_exists="replace", index=False)
    appointments.to_sql(
        "appointments", engine, if_exists="replace", index=False
    )
    triage.to_sql("triage", engine, if_exists="replace", index=False)

    print(f"✓ Saved to {DB_PATH}")
    print(f"  patients={len(patients)}  appointments={len(appointments)}  triage={len(triage)}")


if __name__ == "__main__":
    print("Generating synthetic OPD data …")
    patients     = gen_patients(N_PATIENTS)
    appointments = gen_appointments(patients, N_DAYS)
    triage       = gen_triage(appointments)
    save_to_db(patients, appointments, triage)
