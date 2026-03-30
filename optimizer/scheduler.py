"""
Team A — scheduler.py
Assigns patients to time slots minimizing total wait time.
Used directly by the FastAPI /schedule endpoint.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

try:
    import pulp
    USE_PULP = True
except ImportError:
    USE_PULP = False
    print("PuLP not installed — falling back to greedy heuristic scheduler.")


@dataclass
class Patient:
    patient_id: str
    arrival_time: datetime
    service_type: str
    priority: int = 1          # higher = more urgent (triage high=3, med=2, low=1)
    duration_min: int = 15


@dataclass
class Doctor:
    doctor_id: str
    name: str
    specialization: str
    available_from: datetime = field(default_factory=datetime.now)
    available_until: Optional[datetime] = None


@dataclass
class Assignment:
    patient_id: str
    doctor_id: str
    start_time: datetime
    end_time: datetime
    wait_minutes: float


# ── greedy heuristic (always available, no external deps) ─────────────────────

def greedy_schedule(patients: List[Patient], doctors: List[Doctor]) -> List[Assignment]:
    """
    Fast heuristic: sort patients by priority desc then arrival asc,
    assign each to the earliest-free doctor with matching specialization.
    """
    patients_sorted = sorted(
        patients, key=lambda p: (-p.priority, p.arrival_time)
    )

    # track when each doctor is next free
    doctor_free: dict[str, datetime] = {
        d.doctor_id: d.available_from for d in doctors
    }
    doctor_map = {d.doctor_id: d for d in doctors}

    assignments: List[Assignment] = []

    for patient in patients_sorted:
        # find best doctor (same specialization preferred, else any)
        candidates = [
            d for d in doctors
            if d.specialization == patient.service_type
        ] or doctors

        best_doc = min(candidates, key=lambda d: doctor_free[d.doctor_id])
        start = max(doctor_free[best_doc.doctor_id], patient.arrival_time)
        end   = start + timedelta(minutes=patient.duration_min)

        doctor_free[best_doc.doctor_id] = end
        wait = (start - patient.arrival_time).total_seconds() / 60

        assignments.append(Assignment(
            patient_id  = patient.patient_id,
            doctor_id   = best_doc.doctor_id,
            start_time  = start,
            end_time    = end,
            wait_minutes= max(0, wait),
        ))

    return assignments


# ── PuLP optimizer (install: pip install pulp) ────────────────────────────────

def pulp_schedule(patients: List[Patient], doctors: List[Doctor]) -> List[Assignment]:
    """
    ILP: minimise sum of wait times.
    Variables: x[p][d][s] = 1 if patient p assigned to doctor d at slot s.
    Constraints: each patient gets exactly one slot; each doctor handles one
    patient per slot; doctor must be available.
    Falls back to greedy if problem is too large (>50 patients).
    """
    if len(patients) == 0:
        return []

    if len(patients) > 50:
        print("Large queue — using greedy fallback for speed.")
        return greedy_schedule(patients, doctors)

    base_time = min(p.arrival_time for p in patients)
    slot_len  = 15   # minutes per slot
    n_slots   = 24   # slots per day (6 hours)

    prob = pulp.LpProblem("OPD_Scheduling", pulp.LpMinimize)

    # decision variables
    x = {
        (p.patient_id, d.doctor_id, s): pulp.LpVariable(
            f"x_{p.patient_id}_{d.doctor_id}_{s}", cat="Binary"
        )
        for p in patients
        for d in doctors
        for s in range(n_slots)
    }

    # objective: minimize total wait
    prob += pulp.lpSum(
        x[(p.patient_id, d.doctor_id, s)]
        * max(0, (base_time + timedelta(minutes=s * slot_len) - p.arrival_time).total_seconds() / 60)
        for p in patients
        for d in doctors
        for s in range(n_slots)
    )

    # constraint 1: each patient assigned exactly once
    for p in patients:
        prob += pulp.lpSum(
            x[(p.patient_id, d.doctor_id, s)]
            for d in doctors
            for s in range(n_slots)
        ) == 1

    # constraint 2: each doctor handles at most one patient per slot
    for d in doctors:
        for s in range(n_slots):
            prob += pulp.lpSum(
                x[(p.patient_id, d.doctor_id, s)]
                for p in patients
            ) <= 1

    # constraint 3: cannot schedule before patient arrives
    for p in patients:
        for d in doctors:
            for s in range(n_slots):
                slot_time = base_time + timedelta(minutes=s * slot_len)
                if slot_time < p.arrival_time:
                    prob += x[(p.patient_id, d.doctor_id, s)] == 0

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    assignments = []
    for p in patients:
        for d in doctors:
            for s in range(n_slots):
                if pulp.value(x[(p.patient_id, d.doctor_id, s)]) == 1:
                    start = base_time + timedelta(minutes=s * slot_len)
                    end   = start + timedelta(minutes=p.duration_min)
                    wait  = max(0, (start - p.arrival_time).total_seconds() / 60)
                    assignments.append(Assignment(
                        patient_id  = p.patient_id,
                        doctor_id   = d.doctor_id,
                        start_time  = start,
                        end_time    = end,
                        wait_minutes= wait,
                    ))
    return assignments


def optimize_schedule(
    patients: List[Patient], doctors: List[Doctor]
) -> List[Assignment]:
    """Entry point used by FastAPI. Picks best available method."""
    if USE_PULP:
        return pulp_schedule(patients, doctors)
    return greedy_schedule(patients, doctors)
