"""
Team A — train.py
Trains wait-time regressor and triage classifier, saves as .pkl files.
Run: python models/train.py
"""

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    mean_absolute_error,
    r2_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sqlalchemy import create_engine

DB_PATH  = Path(__file__).parent.parent / "opd.db"
PKL_DIR  = Path(__file__).parent

# ── load data ─────────────────────────────────────────────────────────────────

def load_data():
    engine = create_engine(f"sqlite:///{DB_PATH}")
    appts  = pd.read_sql("SELECT * FROM appointments", engine)
    triage = pd.read_sql("SELECT * FROM triage", engine)
    return appts, triage


# ── wait-time model ───────────────────────────────────────────────────────────

def train_wait_time(appts: pd.DataFrame):
    print("\n── Wait-time model ──────────────────────")

    df = appts.dropna(subset=["wait_minutes"]).copy()

    # encode service_type
    le = LabelEncoder()
    df["service_enc"] = le.fit_transform(df["service_type"])

    features = ["hour_of_day", "day_of_week", "queue_length", "service_enc"]
    X = df[features]
    y = df["wait_minutes"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2  = r2_score(y_test, y_pred)
    print(f"  MAE : {mae:.2f} min")
    print(f"  R²  : {r2:.3f}")

    # save model + encoder together so API can use both
    bundle = {"model": model, "label_encoder": le, "features": features}
    pkl_path = PKL_DIR / "wait_time.pkl"
    with open(pkl_path, "wb") as f:
        pickle.dump(bundle, f)
    print(f"  ✓ saved → {pkl_path}")
    return bundle


# ── triage classifier ─────────────────────────────────────────────────────────

def train_triage(triage: pd.DataFrame):
    print("\n── Triage classifier ────────────────────")

    le = LabelEncoder()
    triage["label"] = le.fit_transform(triage["triage_level"])  # high=0, low=1, medium=2

    features = ["bp_systolic", "heart_rate", "temp_c", "pain_score"]
    df = triage.dropna(subset=features)
    X  = df[features]
    y  = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print(classification_report(y_test, y_pred, target_names=le.classes_))

    bundle = {"model": model, "label_encoder": le, "features": features}
    pkl_path = PKL_DIR / "triage.pkl"
    with open(pkl_path, "wb") as f:
        pickle.dump(bundle, f)
    print(f"  ✓ saved → {pkl_path}")
    return bundle


if __name__ == "__main__":
    appts, triage = load_data()
    train_wait_time(appts)
    train_triage(triage)
    print("\n✓ All models trained and saved.")
