# OPD Management System

Lightweight decision-support prototype for Outpatient Department flow.

## Team structure

| Team | Members | Owns |
|------|---------|------|
| A — Data + Model | 4 (3 coders + 1 non-coder) | data generator, ML models, optimizer, API |
| B — App + Visualize | 2 (2 coders) | Streamlit dashboard |
| C — Docs + Present | 3 (0–1 coder, 2–3 non-coders) | README, slides, test scenarios, demo script |

## Project structure

```
opd_system/
├── data/
│   └── data_generator.py     # generates opd.db
├── models/
│   ├── train.py              # trains wait_time.pkl + triage.pkl
│   ├── wait_time.pkl         # auto-generated
│   └── triage.pkl            # auto-generated
├── optimizer/
│   └── scheduler.py          # PuLP / greedy scheduling
├── api/
│   └── main.py               # FastAPI backend
├── dashboard/
│   └── app.py                # Streamlit frontend
├── tests/
│   └── test_api.py           # pytest suite
├── requirements.txt
└── README.md
```

## Setup (run once)

```bash
# 1. Clone and enter project
cd opd_system

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

## Run order (important — follow this sequence)

### Step 1 — Generate data (Team A)
```bash
python data/data_generator.py
```
Creates `opd.db` with synthetic patients, appointments, and triage records.

### Step 2 — Train models (Team A)
```bash
python models/train.py
```
Produces `models/wait_time.pkl` and `models/triage.pkl`.
Prints MAE, R², and classification report to confirm models trained correctly.

### Step 3 — Start the API (Team A)
```bash
uvicorn api.main:app --reload --port 8000
```
API docs available at: http://localhost:8000/docs

If it still says 3.13, your venv was created with the wrong Python. Recreate it:
bashdeactivate
rm -rf venv
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

### Step 4 — Start the dashboard (Team B)
Open a new terminal:
```bash
streamlit run dashboard/app.py
```
Dashboard opens at: http://localhost:8501

### Step 5 — Run tests (Team C)
Open a third terminal:
```bash
pytest tests/ -v
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Model + DB status check |
| POST | /triage | Urgency classification from vitals |
| POST | /forecast | Predicted wait time |
| POST | /schedule | Optimized appointment schedule |
| GET | /queue | Live queue state |
| GET | /stats | Summary statistics |
| GET | /doctors | Doctor list |

### Example: triage
```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{"bp_systolic": 145, "heart_rate": 100, "temp_c": 38.5, "pain_score": 8}'
```

### Example: wait-time forecast
```bash
curl -X POST http://localhost:8000/forecast \
  -H "Content-Type: application/json" \
  -d '{"service_type": "cardiology", "hour_of_day": 9, "day_of_week": 0, "queue_length": 10}'
```

## Dashboard pages

- **Dashboard** — real-time queue length, appointments table, wait-time chart
- **Triage** — enter vitals → get urgency level + predicted wait
- **Schedule** — add patients → optimize and view Gantt chart
- **Analytics** — wait distribution, no-show rates, hourly arrivals

## Data schema

- `patients` — patient_id, age, gender, acuity
- `appointments` — appt_id, patient_id, arrival_time, service_type, doctor_id, room_id, scheduled/actual times, no_show, wait_minutes
- `triage` — triage_id, appt_id, triage_level, bp_systolic, heart_rate, temp_c, pain_score
- `staff` — doctor_id, name, specialization
- `rooms` — room_id, room_type
- `services` — service_type, duration_min, std

## Datasets referenced

- MIMIC-IV: https://physionet.org/content/mimiciv/3.1/
- Kaggle triage dataset: https://www.kaggle.com/datasets/emirhanakku/synthetic-medical-triage-priority-dataset

## Handoff contract (Team A → Team B)

Team B requires:
1. `opd.db` present in project root
2. `models/wait_time.pkl` and `models/triage.pkl` present
3. API running at `http://localhost:8000`
4. GET /health returns `{"wait_model_loaded": true, "triage_model_loaded": true, "db_exists": true}`
