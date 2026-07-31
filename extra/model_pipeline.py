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

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

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

# Per-district: extra/backtest_all_districts.py runs the holdout method
# separately for each of the 25 districts (climate varies a lot across Sri
# Lanka — coastal vs hill-country vs dry-zone — so one district's bias
# doesn't necessarily transfer to another) and only keeps a district's
# correction if it actually beats the raw model on its own holdout set (165
# origins, 48 days each, fit on the first 70% chronologically, evaluated on
# the untouched last 30%). 19/25 districts get a temperature correction,
# 21/25 get a humidity correction; the rest (e.g. Colombo's temperature: raw
# 0.37 degC MAE beats corrected 0.40) are intentionally absent, meaning zero
# correction, not "not yet done". Computed 2026-07-26. Regenerate both tables
# together (rerun extra/backtest_all_districts.py) if the model is retrained.
ZERO_24 = [0.0] * 24

TEMP_BIAS_CORRECTION_C: dict[str, list[float]] = {
    "Ampara": [-0.507, -0.280, -0.194, -0.307, -0.399, -0.169, -0.451, -0.213, -0.135, -0.266, -0.324, -0.039, -0.283, -0.040, 0.016, -0.143, -0.299, -0.078, -0.356, -0.107, -0.017, -0.146, -0.221, -0.007],
    "Anuradhapura": [-0.472, -0.477, -0.410, -0.364, -0.374, -0.105, -0.393, -0.357, -0.277, -0.239, -0.225, 0.068, -0.197, -0.181, -0.132, -0.133, -0.214, 0.008, -0.301, -0.275, -0.197, -0.161, -0.174, 0.055],
    "Badulla": [-1.061, -0.675, -0.545, -0.562, -0.557, -0.530, -1.067, -0.719, -0.614, -0.647, -0.645, -0.547, -1.069, -0.710, -0.646, -0.717, -0.762, -0.699, -1.227, -0.843, -0.726, -0.698, -0.640, -0.527],
    "Batticaloa": [-0.338, -0.289, -0.279, -0.248, -0.279, 0.001, -0.236, -0.162, -0.137, -0.132, -0.152, 0.159, -0.073, -0.020, -0.041, -0.066, -0.160, 0.104, -0.145, -0.081, -0.070, -0.061, -0.082, 0.158],
    "Galle": [-0.496, -0.366, -0.292, -0.252, -0.289, -0.202, -0.431, -0.276, -0.210, -0.176, -0.158, -0.049, -0.246, -0.136, -0.105, -0.143, -0.216, -0.155, -0.375, -0.237, -0.163, -0.147, -0.173, -0.127],
    "Hambantota": [-0.507, -0.470, -0.388, -0.286, -0.293, -0.112, -0.413, -0.346, -0.245, -0.164, -0.162, 0.082, -0.211, -0.164, -0.106, -0.053, -0.133, 0.043, -0.269, -0.222, -0.140, -0.069, -0.068, 0.075],
    "Kandy": [-0.956, -0.854, -0.746, -0.713, -0.724, -0.480, -0.872, -0.755, -0.645, -0.608, -0.605, -0.362, -0.749, -0.674, -0.612, -0.648, -0.726, -0.528, -0.923, -0.792, -0.674, -0.611, -0.627, -0.435],
    "Kegalle": [-0.758, -0.640, -0.508, -0.544, -0.513, -0.396, -0.759, -0.614, -0.475, -0.485, -0.387, -0.252, -0.580, -0.474, -0.373, -0.458, -0.469, -0.379, -0.718, -0.576, -0.426, -0.442, -0.385, -0.298],
    "Kurunegala": [-0.748, -0.686, -0.567, -0.560, -0.547, -0.322, -0.713, -0.621, -0.501, -0.472, -0.401, -0.164, -0.526, -0.477, -0.395, -0.445, -0.481, -0.297, -0.671, -0.582, -0.475, -0.431, -0.414, -0.229],
    "Matale": [-0.709, -0.679, -0.594, -0.522, -0.506, -0.312, -0.616, -0.564, -0.488, -0.403, -0.349, -0.162, -0.441, -0.428, -0.391, -0.390, -0.441, -0.314, -0.629, -0.570, -0.503, -0.419, -0.409, -0.282],
    "Matara": [-0.480, -0.394, -0.322, -0.272, -0.284, -0.202, -0.408, -0.281, -0.205, -0.158, -0.130, -0.033, -0.216, -0.133, -0.100, -0.115, -0.193, -0.150, -0.356, -0.250, -0.174, -0.120, -0.145, -0.111],
    "Monaragala": [-0.710, -0.509, -0.436, -0.387, -0.408, -0.160, -0.607, -0.412, -0.355, -0.348, -0.392, -0.101, -0.535, -0.347, -0.334, -0.349, -0.452, -0.208, -0.649, -0.431, -0.352, -0.313, -0.347, -0.097],
    "Mullaitivu": [-0.228, -0.231, -0.296, -0.332, -0.251, 0.083, -0.191, -0.140, -0.145, -0.167, -0.064, 0.309, 0.032, 0.057, -0.006, -0.056, -0.010, 0.307, 0.027, 0.061, 0.030, -0.009, 0.046, 0.343],
    "NuwaraEliya": [-1.531, -1.510, -1.346, -1.185, -1.131, -0.931, -1.499, -1.490, -1.310, -1.081, -1.026, -0.839, -1.426, -1.469, -1.381, -1.296, -1.328, -1.187, -1.791, -1.794, -1.595, -1.312, -1.204, -1.038],
    "Polonnaruwa": [-0.436, -0.386, -0.342, -0.213, -0.140, -0.040, -0.370, -0.305, -0.236, -0.117, -0.036, 0.117, -0.193, -0.117, -0.081, 0.033, 0.062, 0.157, -0.170, -0.095, -0.024, 0.094, 0.130, 0.203],
    "Puttalam": [-0.344, -0.243, -0.171, -0.116, -0.162, 0.062, -0.180, -0.054, 0.006, 0.038, 0.024, 0.259, 0.047, 0.139, 0.167, 0.141, 0.027, 0.187, -0.061, 0.035, 0.072, 0.078, 0.001, 0.171],
    "Ratnapura": [-0.757, -0.646, -0.709, -0.622, -0.599, -0.447, -0.769, -0.625, -0.693, -0.591, -0.503, -0.336, -0.610, -0.498, -0.590, -0.578, -0.584, -0.456, -0.726, -0.577, -0.623, -0.518, -0.484, -0.374],
    "Trincomalee": [-0.222, -0.165, -0.309, -0.303, -0.301, 0.016, -0.178, -0.080, -0.181, -0.174, -0.165, 0.195, 0.002, 0.083, -0.065, -0.080, -0.118, 0.202, 0.009, 0.106, -0.003, 0.007, 0.008, 0.299],
    "Vavuniya": [-0.365, -0.486, -0.332, -0.309, -0.307, -0.068, -0.296, -0.374, -0.197, -0.187, -0.170, 0.103, -0.115, -0.207, -0.068, -0.083, -0.133, 0.067, -0.170, -0.249, -0.086, -0.061, -0.064, 0.132],
}
HUMIDITY_BIAS_CORRECTION_PCT: dict[str, list[float]] = {
    "Ampara": [-0.117, -0.651, -1.397, -0.789, -0.292, -1.616, -0.184, -0.937, -1.753, -1.147, -0.873, -2.402, -1.188, -2.063, -3.000, -2.364, -1.719, -2.976, -1.614, -2.444, -3.363, -2.606, -2.078, -3.033],
    "Anuradhapura": [-0.228, 0.201, 0.068, -0.129, -0.298, -1.350, -0.173, -0.096, -0.452, -0.718, -1.091, -2.310, -1.331, -1.336, -1.802, -2.074, -2.158, -3.103, -1.957, -1.945, -2.337, -2.476, -2.543, -3.227],
    "Badulla": [1.735, 1.062, -0.184, -0.563, -0.926, -0.339, 2.017, 1.222, -0.156, -0.680, -1.180, -0.932, 1.144, 0.152, -1.267, -1.670, -2.045, -1.726, 0.495, -0.445, -1.767, -2.229, -2.653, -2.173],
    "Colombo": [0.154, 0.438, -0.311, -0.819, -1.026, -1.087, -0.155, -0.098, -0.879, -1.404, -1.859, -2.039, -1.231, -1.085, -1.811, -2.058, -2.106, -2.108, -1.281, -1.207, -1.992, -2.228, -2.204, -2.026],
    "Galle": [-0.131, -0.097, -0.627, -0.969, -0.773, -0.923, -0.190, -0.443, -1.089, -1.469, -1.525, -1.928, -1.361, -1.561, -2.101, -2.280, -1.978, -2.093, -1.441, -1.644, -2.227, -2.423, -2.155, -1.924],
    "Kalutara": [0.103, 0.377, -0.051, -0.123, -0.359, -0.200, 0.244, 0.191, -0.342, -0.485, -1.046, -1.058, -0.790, -0.794, -1.168, -1.159, -1.301, -1.061, -0.702, -0.734, -1.216, -1.368, -1.495, -1.062],
    "Kandy": [1.311, 1.547, 1.002, 0.589, 0.563, -0.949, 1.003, 1.007, 0.271, -0.229, -0.410, -2.044, -0.231, -0.227, -0.876, -1.151, -0.980, -2.298, -0.338, -0.406, -1.138, -1.576, -1.351, -2.358],
    "Kegalle": [0.560, 0.850, 0.029, 0.001, -0.134, -0.236, 0.873, 0.843, -0.172, -0.364, -0.843, -1.115, -0.240, -0.265, -1.214, -1.196, -1.227, -1.227, -0.272, -0.320, -1.308, -1.412, -1.525, -1.338],
    "Kilinochchi": [-0.808, -0.882, -1.704, -2.326, -2.070, -3.045, -1.586, -1.980, -2.972, -3.584, -3.384, -4.463, -3.013, -3.343, -4.311, -4.897, -4.569, -5.479, -3.926, -4.176, -4.926, -5.132, -4.626, -5.215],
    "Kurunegala": [0.743, 0.946, 0.615, 0.138, -0.159, -0.590, 0.936, 0.842, 0.329, -0.287, -0.913, -1.508, -0.189, -0.290, -0.754, -1.171, -1.358, -1.667, -0.261, -0.427, -0.840, -1.398, -1.644, -1.744],
    "Mannar": [-0.376, -0.651, -1.103, -1.344, -1.207, -1.789, -0.687, -1.237, -1.743, -1.948, -2.050, -2.736, -1.773, -2.282, -2.786, -2.860, -2.550, -2.940, -1.814, -2.189, -2.518, -2.452, -2.122, -2.358],
    "Matale": [0.602, 0.822, 0.787, 0.316, 0.074, -0.811, 0.462, 0.473, 0.325, -0.192, -0.655, -1.655, -0.561, -0.575, -0.635, -0.935, -0.955, -1.598, -0.397, -0.498, -0.627, -1.100, -1.216, -1.645],
    "Matara": [0.061, 0.070, -0.129, -0.555, -0.613, -0.602, 0.160, -0.171, -0.549, -1.058, -1.387, -1.585, -1.021, -1.341, -1.660, -2.042, -1.987, -1.912, -1.263, -1.557, -1.886, -2.346, -2.298, -1.872],
    "Monaragala": [0.702, 0.194, 0.072, -0.355, -0.357, -1.382, 0.714, -0.022, -0.283, -0.749, -0.753, -1.986, -0.065, -0.877, -1.201, -1.695, -1.560, -2.712, -0.719, -1.544, -1.960, -2.381, -2.228, -3.059],
    "Mullaitivu": [-1.589, -1.674, -1.218, -0.708, -1.134, -2.694, -1.861, -2.376, -2.285, -1.964, -2.549, -4.194, -3.354, -3.774, -3.605, -3.212, -3.623, -5.122, -4.189, -4.508, -4.259, -3.658, -3.848, -5.028],
    "NuwaraEliya": [2.871, 2.994, 2.559, 1.535, 0.950, -0.304, 2.470, 2.653, 2.063, 0.810, 0.195, -1.284, 1.301, 1.446, 1.062, 0.351, 0.109, -0.979, 1.880, 2.214, 1.443, 0.109, -0.496, -1.474],
    "Polonnaruwa": [-1.381, -1.512, -1.580, -2.114, -2.587, -3.383, -2.195, -2.581, -2.828, -3.472, -3.964, -4.755, -3.606, -4.004, -4.276, -4.907, -5.239, -5.880, -4.588, -4.815, -5.033, -5.368, -5.447, -5.744],
    "Puttalam": [-0.312, -0.740, -1.107, -1.613, -1.476, -2.344, -0.952, -1.645, -2.077, -2.524, -2.579, -3.505, -2.247, -2.880, -3.298, -3.578, -3.275, -3.900, -2.495, -3.080, -3.348, -3.516, -3.112, -3.586],
    "Ratnapura": [1.582, 2.125, 2.240, 1.762, 1.232, 0.412, 1.878, 2.127, 2.090, 1.495, 0.601, -0.392, 0.786, 0.981, 0.997, 0.667, 0.232, -0.435, 0.769, 0.976, 0.966, 0.422, -0.018, -0.464],
    "Trincomalee": [-1.533, -1.455, -0.646, -0.532, -0.589, -2.422, -1.931, -2.254, -1.745, -1.758, -1.918, -3.855, -3.383, -3.618, -3.075, -3.035, -3.042, -4.872, -4.323, -4.460, -3.863, -3.606, -3.538, -4.982],
    "Vavuniya": [-0.682, 0.192, -0.614, -0.713, -0.715, -1.905, -0.844, -0.329, -1.359, -1.525, -1.664, -3.004, -2.065, -1.565, -2.665, -2.826, -2.797, -3.898, -2.853, -2.310, -3.313, -3.368, -3.244, -4.026],
}


def clamp_physical(
    temp: float,
    rain: float,
    humidity: float,
    hour_index: int | None = None,
    district: str | None = None,
) -> tuple[float, float, float]:
    if hour_index is not None:
        temp += TEMP_BIAS_CORRECTION_C.get(district, ZERO_24)[hour_index]
        humidity += HUMIDITY_BIAS_CORRECTION_PCT.get(district, ZERO_24)[hour_index]

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


# ──────────────────────────────────────────────────────────────────────────────
# WeatherAPI.com — mirrors Backend/forecast/repositories.py's WeatherRepository
# ──────────────────────────────────────────────────────────────────────────────

WEATHERAPI_BASE_URL = "https://api.weatherapi.com/v1"
# WeatherAPI's free/standard plans expose no solar-irradiance (W/m2) field, so
# DaylightScore is approximated from UV index instead — 11 is a "very high"
# tropical UV reading. Mirrors Backend/forecast/repositories.py exactly.
MAX_UV_INDEX = 11.0


def load_weatherapi_key() -> str:
    """Reads WEATHERAPI_KEY from the environment, falling back to Backend/.env."""
    key = os.environ.get("WEATHERAPI_KEY", "").strip()
    if key:
        return key

    env_path = BASE_DIR.parent / "Backend" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("WEATHERAPI_KEY="):
                value = line.split("=", 1)[1].strip()
                if value:
                    return value

    raise RuntimeError(
        "No WeatherAPI key found. Set the WEATHERAPI_KEY environment variable, "
        "or add WEATHERAPI_KEY=... to Backend/.env (get a free key at "
        "https://www.weatherapi.com/signup.aspx)."
    )


def _weatherapi_get(path: str, params: dict, key: str) -> dict:
    resp = requests.get(f"{WEATHERAPI_BASE_URL}/{path}", params={**params, "key": key}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _frame_from_weatherapi_hours(hours: List[dict]) -> pd.DataFrame:
    df = pd.DataFrame({
        "datetime": pd.to_datetime([h["time"] for h in hours]),
        "Temperature_C": [h["temp_c"] for h in hours],
        "Precipitation_mm": [h["precip_mm"] for h in hours],
        "Humidity_%": [h["humidity"] for h in hours],
        "CloudCover_%": [h["cloud"] for h in hours],
        "WindSpeed_kmh": [h["wind_kph"] for h in hours],
        "WindGusts_kmh": [h["gust_kph"] for h in hours],
        "DaylightScore": [(h["uv"] / MAX_UV_INDEX) if h.get("is_day") else 0.0 for h in hours],
    })
    # Independent calls (history x7 + forecast) can overlap at day boundaries.
    df = df.drop_duplicates(subset="datetime").sort_values("datetime").reset_index(drop=True)
    df["DaylightScore"] = df["DaylightScore"].clip(0.0, 1.0)
    df["Hour"] = df["datetime"].dt.hour
    df["Month"] = df["datetime"].dt.month
    return df


def fetch_weatherapi(district: str, key: str, forecast_days: int = 2) -> pd.DataFrame:
    """168h of real observations (7 history days + today) PLUS WeatherAPI's own
    forecast for `forecast_days` ahead, all in one frame — mirrors
    Backend/forecast/repositories.py's WeatherRepository.fetch_context_window."""
    if district not in DISTRICT_COORDS:
        raise ValueError(f"Unknown district: '{district}'. See DISTRICT_COORDS.")

    coords = DISTRICT_COORDS[district]
    q = f"{coords['lat']},{coords['lon']}"
    today = datetime.now(ZoneInfo("Asia/Colombo")).date()

    forecast_payload = _weatherapi_get(
        "forecast.json", {"q": q, "days": forecast_days, "aqi": "no", "alerts": "no"}, key
    )
    history_payloads = [
        _weatherapi_get("history.json", {"q": q, "dt": (today - timedelta(days=d)).isoformat()}, key)
        for d in range(1, 8)
    ]

    hours: List[dict] = []
    for forecastday in forecast_payload["forecast"]["forecastday"]:
        hours.extend(forecastday["hour"])
    for payload in history_payloads:
        hours.extend(payload["forecast"]["forecastday"][0]["hour"])

    return _frame_from_weatherapi_hours(hours)


def fetch_weatherapi_actual(district: str, dates: List, key: str) -> pd.DataFrame:
    """Real recorded observations for specific calendar dates, via WeatherAPI's
    history endpoint. Used as ground truth once a prediction window has
    elapsed — `dates` is a list of `datetime.date` objects."""
    if district not in DISTRICT_COORDS:
        raise ValueError(f"Unknown district: '{district}'. See DISTRICT_COORDS.")

    coords = DISTRICT_COORDS[district]
    q = f"{coords['lat']},{coords['lon']}"

    hours: List[dict] = []
    for d in dates:
        payload = _weatherapi_get("history.json", {"q": q, "dt": d.isoformat()}, key)
        hours.extend(payload["forecast"]["forecastday"][0]["hour"])

    return _frame_from_weatherapi_hours(hours)


def predict_next_24h(district: str) -> Dict[str, Any]:
    """Fetch context, run the GRU, return the 24h prediction + timestamps."""
    df = fetch_open_meteo(district, forecast_days=1)
    context, _ = split_context_and_future(df)

    real = run_model(context)
    last_obs = context["datetime"].iloc[-1].to_pydatetime()

    rows = []
    for i in range(TARGET_HORIZON):
        temp, rain, humidity = clamp_physical(
            real[i][0], real[i][1], real[i][2], hour_index=i, district=district
        )
        valid = last_obs + pd.Timedelta(hours=i + 1)
        rows.append({
            "valid_time": valid,
            "temperature_c": temp,
            "precipitation_mm": rain,
            "humidity_pct": humidity,
        })

    return {"district": district, "last_observation": last_obs, "forecast": rows}
