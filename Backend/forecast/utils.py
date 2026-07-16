"""
forecast.utils
──────────────
Pure, dependency-free helpers: no I/O, no FastAPI, no Supabase.

Everything that must EXACTLY mirror the training pipeline lives here, in one
place. If `1_prepare_forecast.py` ever changes, this is the only file that has
to change with it — get these wrong and the model silently returns nonsense
rather than failing loudly.
"""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# Districts — Open-Meteo works from lat/lon
# ──────────────────────────────────────────────────────────────────────────────

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

# ──────────────────────────────────────────────────────────────────────────────
# Feature contract — the order is STRUCTURAL. Do not sort, do not "tidy".
# ──────────────────────────────────────────────────────────────────────────────

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
TARGET_INDICES: List[int] = [FINAL_FEATURE_COLS.index(c) for c in TARGET_COLS]  # [0, 1, 2]

# Sri Lanka peaks around ~1000 W/m² of direct radiation; used to normalise daylight.
MAX_RADIATION_WM2 = 1000.0


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Raw hourly observations → the 12 model features, in the fixed order.

    Cyclical encodings keep hour 23 adjacent to hour 0 (and December adjacent to
    January), which a raw integer cannot express. `Temp_Change_3h` is an
    atmospheric-momentum proxy computed only within this contiguous window; the
    first three rows have no prior context and get 0.0, exactly as in training.
    """
    df = df.copy()

    df["Hour_sin"] = np.sin(2 * np.pi * df["Hour"] / 24.0)
    df["Hour_cos"] = np.cos(2 * np.pi * df["Hour"] / 24.0)
    df["Month_sin"] = np.sin(2 * np.pi * df["Month"] / 12.0)
    df["Month_cos"] = np.cos(2 * np.pi * df["Month"] / 12.0)

    df["Temp_Change_3h"] = df["Temperature_C"].diff(periods=3).fillna(0.0)

    return df[FINAL_FEATURE_COLS]


def inverse_transform_targets(raw_pred: np.ndarray, scaler: Any, horizon: int) -> np.ndarray:
    """(H, 3) scaled predictions → (H, 3) real units.

    The scaler was fitted on all 12 features, so `inverse_transform` insists on
    12 columns. We slot the 3 predicted channels into their original positions in
    a zero matrix, invert the lot, then pull those 3 columns back out.
    """
    placeholder = np.zeros((horizon, len(FINAL_FEATURE_COLS)), dtype=np.float32)
    for out_idx, feat_idx in enumerate(TARGET_INDICES):
        placeholder[:, feat_idx] = raw_pred[:, out_idx]

    real_values = scaler.inverse_transform(placeholder)
    return real_values[:, TARGET_INDICES]


def clamp_physical(temp: float, rain: float, humidity: float) -> tuple[float, float, float]:
    """The model is a regressor: nothing stops it predicting -2 mm of rain.
    Physics does. Clamp before anyone sees a number."""
    return (
        round(float(temp), 1),
        round(max(0.0, float(rain)), 3),
        round(min(100.0, max(0.0, float(humidity))), 1),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Travel advisory — the thresholds from the reference runner, kept identical
# ──────────────────────────────────────────────────────────────────────────────

ADVISORY_GOOD = "GOOD"
ADVISORY_CAUTION = "CAUTION"
ADVISORY_AVOID = "AVOID"


def hourly_advisory(temp: float, rain: float, humidity: float) -> Dict[str, str]:
    """Turn three numbers into a decision a traveler can act on."""
    if rain > 10.0:
        return {"level": ADVISORY_AVOID, "reason": "Heavy rain"}
    if rain > 3.0:
        return {"level": ADVISORY_CAUTION, "reason": "Light rain"}
    if humidity > 85.0:
        return {"level": ADVISORY_CAUTION, "reason": "Very humid"}
    if temp > 35.0:
        return {"level": ADVISORY_CAUTION, "reason": "Extreme heat"}
    return {"level": ADVISORY_GOOD, "reason": "Clear conditions"}


# ──────────────────────────────────────────────────────────────────────────────
# WMO weather codes — Open-Meteo's `current` block reports a code, not text.
# ──────────────────────────────────────────────────────────────────────────────

WMO_CODE_TEXT: Dict[int, str] = {
    0: "Clear sky", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
    56: "Freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Slight rain showers", 81: "Rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Severe thunderstorm with hail",
}


def weather_condition_text(code: int) -> str:
    return WMO_CODE_TEXT.get(int(code), "Unknown")


def daily_summary(forecast: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Roll 24 hours up into the one line a traveler actually reads."""
    temps = [h["temperature_c"] for h in forecast]
    rains = [h["precipitation_mm"] for h in forecast]
    humids = [h["humidity_pct"] for h in forecast]

    total_rain = sum(rains)

    if total_rain > 20:
        level, verdict = ADVISORY_AVOID, "Not recommended for travel"
    elif total_rain > 5:
        level, verdict = ADVISORY_CAUTION, "Travel with caution"
    else:
        level, verdict = ADVISORY_GOOD, "Good day to travel"

    wet_hours = sum(1 for r in rains if r > 0.5)

    return {
        "temp_min_c": round(min(temps), 1),
        "temp_max_c": round(max(temps), 1),
        "temp_avg_c": round(sum(temps) / len(temps), 1),
        "total_rain_mm": round(total_rain, 2),
        "humidity_min_pct": round(min(humids), 1),
        "humidity_max_pct": round(max(humids), 1),
        "wet_hours": wet_hours,
        "advisory_level": level,
        "verdict": verdict,
    }
