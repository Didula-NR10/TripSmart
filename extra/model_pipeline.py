"""
model_pipeline.py
──────────────────
Standalone copy of the TripSmart GRU forecaster pipeline — this is the exact
same feature engineering / inference logic used by Backend/forecast/utils.py
and Backend/forecast/repositories.py, extracted so it can run on its own in a
terminal with no FastAPI, no Supabase, no backend server required.

Nothing here talks to the Backend or Frontend folders. It reads the model
artifacts from ./models (a copy of Backend/models) and hits Open-Meteo's free,
keyless API directly with `requests`.

If you ever retrain the model, drop the new best_checkpoint.keras / scaler.pkl
into extra/models/ to update this copy too.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "best_checkpoint.keras"
SCALER_PATH = BASE_DIR / "models" / "scaler.pkl"

INPUT_WINDOW = 168
TARGET_HORIZON = 24

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_FIELDS = [
    "temperature_2m",
    "precipitation",
    "relativehumidity_2m",
    "cloudcover",
    "windspeed_10m",
    "windgusts_10m",
    "direct_radiation",
]
MAX_RADIATION_WM2 = 1000.0

DISTRICT_COORDS: Dict[str, Dict[str, float]] = {
    "Colombo":      {"lat": 6.9271, "lon": 79.8612},
    "Gampaha":      {"lat": 7.0873, "lon": 79.9997},
    "Kalutara":     {"lat": 6.5854, "lon": 79.9607},
    "Kandy":        {"lat": 7.2906, "lon": 80.6337},
    "Matale":       {"lat": 7.4675, "lon": 80.6234},
    "NuwaraEliya":  {"lat": 6.9497, "lon": 80.7891},
    "Galle":        {"lat": 6.0535, "lon": 80.2210},
    "Matara":       {"lat": 5.9549, "lon": 80.5550},
    "Hambantota":   {"lat": 6.1241, "lon": 81.1185},
    "Jaffna":       {"lat": 9.6615, "lon": 80.0255},
    "Kilinochchi":  {"lat": 9.3803, "lon": 80.3770},
    "Mannar":       {"lat": 8.9810, "lon": 79.9044},
    "Vavuniya":     {"lat": 8.7514, "lon": 80.4971},
    "Mullaitivu":   {"lat": 9.2671, "lon": 80.8128},
    "Batticaloa":   {"lat": 7.7170, "lon": 81.7000},
    "Ampara":       {"lat": 7.2977, "lon": 81.6724},
    "Trincomalee":  {"lat": 8.5874, "lon": 81.2152},
    "Kurunegala":   {"lat": 7.4867, "lon": 80.3647},
    "Puttalam":     {"lat": 8.0362, "lon": 79.8283},
    "Anuradhapura": {"lat": 8.3114, "lon": 80.4037},
    "Polonnaruwa":  {"lat": 7.9403, "lon": 81.0188},
    "Badulla":      {"lat": 6.9934, "lon": 81.0550},
    "Monaragala":   {"lat": 6.8728, "lon": 81.3507},
    "Ratnapura":    {"lat": 6.6828, "lon": 80.3992},
    "Kegalle":      {"lat": 7.2513, "lon": 80.3464},
}

# Feature contract — the order is STRUCTURAL, mirrors Backend/forecast/utils.py.
FINAL_FEATURE_COLS: List[str] = [
    "Temperature_C",
    "Precipitation_mm",
    "Humidity_%",
    "CloudCover_%",
    "WindSpeed_kmh",
    "WindGusts_kmh",
    "DaylightScore",
    "Hour_sin",
    "Hour_cos",
    "Month_sin",
    "Month_cos",
    "Temp_Change_3h",
]

TARGET_COLS: List[str] = ["Temperature_C", "Precipitation_mm", "Humidity_%"]
TARGET_INDICES: List[int] = [FINAL_FEATURE_COLS.index(c) for c in TARGET_COLS]


# ──────────────────────────────────────────────────────────────────────────────
# Model + scaler — loaded once, lazily (TensorFlow import is slow/heavy)
# ──────────────────────────────────────────────────────────────────────────────

_model = None
_scaler = None


def get_model():
    global _model
    if _model is None:
        import tensorflow as tf

        print(f"Loading GRU forecaster from {MODEL_PATH} ...")
        _model = tf.keras.models.load_model(MODEL_PATH)
        dummy = np.zeros((1, INPUT_WINDOW, 12), dtype=np.float32)
        _model.predict(dummy, verbose=0)
        print(f"Model ready. Input shape: {_model.input_shape}")
    return _model


def get_scaler():
    global _scaler
    if _scaler is None:
        import joblib

        print(f"Loading scaler from {SCALER_PATH} ...")
        scaler = joblib.load(SCALER_PATH)
        if scaler.n_features_in_ != 12:
            raise ValueError(
                f"Scaler was fitted on {scaler.n_features_in_} features, expected 12."
            )
        _scaler = scaler
    return _scaler


# ──────────────────────────────────────────────────────────────────────────────
# Feature engineering — identical to Backend/forecast/utils.py
# ──────────────────────────────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Hour_sin"] = np.sin(2 * np.pi * df["Hour"] / 24.0)
    df["Hour_cos"] = np.cos(2 * np.pi * df["Hour"] / 24.0)
    df["Month_sin"] = np.sin(2 * np.pi * df["Month"] / 12.0)
    df["Month_cos"] = np.cos(2 * np.pi * df["Month"] / 12.0)
    df["Temp_Change_3h"] = df["Temperature_C"].diff(periods=3).fillna(0.0)
    return df[FINAL_FEATURE_COLS]


def inverse_transform_targets(raw_pred: np.ndarray, scaler: Any, horizon: int) -> np.ndarray:
    placeholder = np.zeros((horizon, len(FINAL_FEATURE_COLS)), dtype=np.float32)
    for out_idx, feat_idx in enumerate(TARGET_INDICES):
        placeholder[:, feat_idx] = raw_pred[:, out_idx]
    real_values = scaler.inverse_transform(placeholder)
    return real_values[:, TARGET_INDICES]


# Mirrors Backend/forecast/utils.py — keep both in sync.
RAIN_ZERO_FLOOR_MM = 0.3

# See Backend/forecast/utils.py for the full history of these values. Short
# version: a single-snapshot comparison against Open-Meteo's own forecast
# suggested a large temperature correction, but backtest.py's proper
# train/holdout validation against Open-Meteo's historical archive (real
# ground truth, 165 origins over 48 days) showed the raw model beats every
# temperature correction tried (holdout MAE 0.37 degC raw vs 0.72 corrected)
# — so temperature correction is left at zero. Humidity's bias held up
# out-of-sample (3.69% raw -> 3.08% corrected) and is populated below.
# Computed 2026-07-26 for Colombo.
TEMP_BIAS_CORRECTION_C = [0.0] * 24
HUMIDITY_BIAS_CORRECTION_PCT = [
    0.154, 0.438, -0.311, -0.819, -1.026, -1.087, -0.155, -0.098,
    -0.879, -1.404, -1.859, -2.039, -1.231, -1.085, -1.811, -2.058,
    -2.106, -2.108, -1.281, -1.207, -1.992, -2.228, -2.204, -2.026,
]


def clamp_physical(
    temp: float, rain: float, humidity: float, hour_index: int | None = None
) -> tuple[float, float, float]:
    if hour_index is not None:
        temp += TEMP_BIAS_CORRECTION_C[hour_index]
        humidity += HUMIDITY_BIAS_CORRECTION_PCT[hour_index]

    if rain <= RAIN_ZERO_FLOOR_MM:
        rain = 0.0

    return (
        round(float(temp), 1),
        round(max(0.0, float(rain)), 3),
        round(min(100.0, max(0.0, float(humidity))), 1),
    )


def run_model(frame: pd.DataFrame) -> np.ndarray:
    """168 rows of raw observations -> (24, 3) real-unit predictions [temp, rain, humidity]."""
    engineered = engineer_features(frame)
    if engineered.isnull().any().any():
        raise ValueError("Gaps in the input window produced NaNs after feature engineering.")

    scaler = get_scaler()
    model = get_model()

    scaled = scaler.transform(engineered.values).astype(np.float32)
    tensor = scaled[np.newaxis, :, :]

    expected = (1, INPUT_WINDOW, 12)
    if tensor.shape != expected:
        raise ValueError(f"Tensor shape {tensor.shape}, expected {expected}.")

    raw = model.predict(tensor, verbose=0)[0].astype(np.float32)
    raw = np.clip(raw, 0.0, 1.0)
    return inverse_transform_targets(raw, scaler, TARGET_HORIZON)


# ──────────────────────────────────────────────────────────────────────────────
# Open-Meteo — fetch both the past context window AND Open-Meteo's own future
# forecast in one call (forecast_days=2 buys the 24h-ahead comparison window).
# ──────────────────────────────────────────────────────────────────────────────

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def _parse_hourly(hourly: dict) -> pd.DataFrame:
    df = pd.DataFrame({
        "datetime": pd.to_datetime(hourly["time"]),
        "Temperature_C": hourly["temperature_2m"],
        "Precipitation_mm": hourly["precipitation"],
        "Humidity_%": hourly["relativehumidity_2m"],
        "CloudCover_%": hourly["cloudcover"],
        "WindSpeed_kmh": hourly["windspeed_10m"],
        "WindGusts_kmh": hourly["windgusts_10m"],
        "radiation": hourly["direct_radiation"],
    })
    df = df.ffill().bfill()
    df["Hour"] = df["datetime"].dt.hour
    df["Month"] = df["datetime"].dt.month
    df["DaylightScore"] = (df["radiation"] / MAX_RADIATION_WM2).clip(0.0, 1.0)
    return df


def fetch_open_meteo(district: str, forecast_days: int = 2) -> pd.DataFrame:
    """Live forecast endpoint — past_days of real observations + Open-Meteo's
    own forecast for the days ahead. Open-Meteo's forecast is a proxy for
    truth (it hasn't happened yet either), not ground truth."""
    if district not in DISTRICT_COORDS:
        raise ValueError(f"Unknown district: '{district}'. See DISTRICT_COORDS.")

    coords = DISTRICT_COORDS[district]
    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "hourly": ",".join(HOURLY_FIELDS),
        "past_days": 7,
        "forecast_days": forecast_days,
        "timezone": "Asia/Colombo",
        "windspeed_unit": "kmh",
    }

    resp = requests.get(OPEN_METEO_URL, params=params, timeout=15)
    resp.raise_for_status()
    return _parse_hourly(resp.json()["hourly"])


def fetch_archive(district: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Historical reanalysis (ERA5-based) — what actually happened, per
    Open-Meteo's archive. This is real ground truth, unlike the forecast
    endpoint's future rows. `start_date`/`end_date` are 'YYYY-MM-DD'."""
    if district not in DISTRICT_COORDS:
        raise ValueError(f"Unknown district: '{district}'. See DISTRICT_COORDS.")

    coords = DISTRICT_COORDS[district]
    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "hourly": ",".join(HOURLY_FIELDS),
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "Asia/Colombo",
        "windspeed_unit": "kmh",
    }

    resp = requests.get(ARCHIVE_URL, params=params, timeout=30)
    resp.raise_for_status()
    return _parse_hourly(resp.json()["hourly"])


def split_context_and_future(df: pd.DataFrame):
    """Split one fetched frame into (168h past context, rows at/after now)."""
    now = pd.Timestamp.now(tz="Asia/Colombo").tz_localize(None)
    context = df[df["datetime"] <= now].tail(INPUT_WINDOW).reset_index(drop=True)
    future = df[df["datetime"] > now].reset_index(drop=True)

    if len(context) < INPUT_WINDOW:
        raise RuntimeError(
            f"Only {len(context)} hours of past observations available; {INPUT_WINDOW} are required."
        )
    return context, future


def predict_next_24h(district: str) -> Dict[str, Any]:
    """Fetch context, run the GRU, return the 24h prediction + timestamps."""
    df = fetch_open_meteo(district, forecast_days=1)
    context, _ = split_context_and_future(df)

    real = run_model(context)
    last_obs = context["datetime"].iloc[-1].to_pydatetime()

    rows = []
    for i in range(TARGET_HORIZON):
        temp, rain, humidity = clamp_physical(real[i][0], real[i][1], real[i][2], hour_index=i)
        valid = last_obs + pd.Timedelta(hours=i + 1)
        rows.append({
            "valid_time": valid,
            "temperature_c": temp,
            "precipitation_mm": rain,
            "humidity_pct": humidity,
        })

    return {"district": district, "last_observation": last_obs, "forecast": rows}
