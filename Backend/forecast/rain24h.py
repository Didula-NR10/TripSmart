from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

DISTRICT_CLIMATE_ZONE: Dict[str, int] = {
    "Colombo": 1, "Galle": 1, "Gampaha": 1, "Kalutara": 1, "Matara": 1,
    "Ampara": 2, "Anuradhapura": 2, "Batticaloa": 2, "Hambantota": 2,
    "Jaffna": 2, "Kilinochchi": 2, "Mannar": 2, "Monaragala": 2,
    "Polonnaruwa": 2, "Puttalam": 2, "Trincomalee": 2, "Vavuniya": 2,
    "Mullaitivu": 2,
    "Kandy": 3, "Kegalle": 3, "Kurunegala": 3, "Matale": 3, "Ratnapura": 3,
    "Badulla": 4, "NuwaraEliya": 4,
}

ZONE_PEAK_MONTHS: Dict[int, set] = {
    1: {1, 2, 3, 12},
    2: {5, 6, 7, 8, 9},
    3: {1, 2, 7, 8, 12},
    4: {1, 2, 3, 4},
}

CLIMATE_ZONES: List[int] = [1, 2, 3, 4]

_APPARENT_TEMP_BIAS_C = 0.9855

RAIN_ZERO_FLOOR_MM = 0.3

FEATURE_COLS: List[str] = [
    "Temperature_C", "Precipitation_mm", "Humidity_%", "CloudCover_%",
    "WindSpeed_kmh", "WindGusts_kmh", "DaylightScore",
    "Hour_sin", "Hour_cos", "Month_sin", "Month_cos", "Temp_Change_3h",
    "ApparentTemp_C", "ApparentTemp_Diff",
    *[f"ClimateZone_{z}" for z in CLIMATE_ZONES],
    "IsPeakSeason",
    "Rain_lag_1h", "Rain_lag_3h", "Rain_lag_6h",
    "Rain_rolling_6h", "Rain_rolling_24h",
    "Rain_rolling_48h", "Rain_rolling_72h",
    "Temp_Trend_24h", "Humidity_Trend_24h",
]
N_FEATURES = len(FEATURE_COLS)
INPUT_WINDOW = 168
TARGET_HORIZON = 24

def apparent_temperature(temp_c, humidity_pct, wind_kmh):
    wind_ms = wind_kmh / 3.6
    vapour_pressure = (humidity_pct / 100.0) * 6.105 * np.exp(
        17.27 * temp_c / (237.7 + temp_c)
    )
    return temp_c + 0.33 * vapour_pressure - 0.70 * wind_ms - 4.0 + _APPARENT_TEMP_BIAS_C

def is_peak_season(district: str, month: int) -> int:
    zone = DISTRICT_CLIMATE_ZONE.get(district)
    if zone is None:
        return 0
    return 1 if month in ZONE_PEAK_MONTHS[zone] else 0

def engineer_rain24h_features(frame: pd.DataFrame, district: str) -> pd.DataFrame:
    df = frame.copy().reset_index(drop=True)

    df["Hour_sin"] = np.sin(2 * np.pi * df["Hour"] / 24.0)
    df["Hour_cos"] = np.cos(2 * np.pi * df["Hour"] / 24.0)
    df["Month_sin"] = np.sin(2 * np.pi * df["Month"] / 12.0)
    df["Month_cos"] = np.cos(2 * np.pi * df["Month"] / 12.0)
    df["Temp_Change_3h"] = df["Temperature_C"].diff(periods=3).fillna(0.0)

    df["ApparentTemp_C"] = apparent_temperature(
        df["Temperature_C"], df["Humidity_%"], df["WindSpeed_kmh"]
    )
    df["ApparentTemp_Diff"] = df["ApparentTemp_C"] - df["Temperature_C"]

    zone = DISTRICT_CLIMATE_ZONE.get(district)
    for z in CLIMATE_ZONES:
        df[f"ClimateZone_{z}"] = 1.0 if z == zone else 0.0

    df["IsPeakSeason"] = df["Month"].apply(lambda m: is_peak_season(district, int(m)))

    df["Rain_lag_1h"] = df["Precipitation_mm"].shift(1).fillna(0.0)
    df["Rain_lag_3h"] = df["Precipitation_mm"].shift(3).fillna(0.0)
    df["Rain_lag_6h"] = df["Precipitation_mm"].shift(6).fillna(0.0)
    df["Rain_rolling_6h"] = df["Precipitation_mm"].rolling(6, min_periods=1).sum()
    df["Rain_rolling_24h"] = df["Precipitation_mm"].rolling(24, min_periods=1).sum()
    df["Rain_rolling_48h"] = df["Precipitation_mm"].rolling(48, min_periods=1).sum()
    df["Rain_rolling_72h"] = df["Precipitation_mm"].rolling(72, min_periods=1).sum()

    df["Temp_Trend_24h"] = df["Temperature_C"].diff(periods=24).fillna(0.0)
    df["Humidity_Trend_24h"] = df["Humidity_%"].diff(periods=24).fillna(0.0)

    return df[FEATURE_COLS]

DAY_TYPE_RAINY = "RAINY"
DAY_TYPE_SUNNY = "SUNNY"
DAY_TYPE_OVERCAST = "OVERCAST"
DAY_TYPE_STORM_RISK = "HOT_HUMID_STORM_RISK"
DAY_TYPE_MILD = "MILD"

TEMP_TREND_THRESHOLD_C = 0.5
HUMIDITY_TREND_THRESHOLD_PCT = 3.0

RAIN_LOW_MAX_MM = 2.0
RAIN_MODERATE_MAX_MM = 8.0

def _temp_direction(temp_trend_c: float) -> str:
    if temp_trend_c <= -TEMP_TREND_THRESHOLD_C:
        return "falling"
    if temp_trend_c >= TEMP_TREND_THRESHOLD_C:
        return "rising"
    return "stable"

def _humidity_direction(humidity_trend_pct: float) -> str:
    if humidity_trend_pct >= HUMIDITY_TREND_THRESHOLD_PCT:
        return "rising"
    if humidity_trend_pct <= -HUMIDITY_TREND_THRESHOLD_PCT:
        return "falling"
    return "stable"

def _rain_band(rain_mm: float) -> str:
    if rain_mm <= RAIN_LOW_MAX_MM:
        return "low"
    if rain_mm <= RAIN_MODERATE_MAX_MM:
        return "moderate"
    return "high"

def classify_day_type(temp_trend_c: float, humidity_trend_pct: float, rain_high_mm: float) -> Dict[str, str]:
    temp_dir = _temp_direction(temp_trend_c)
    hum_dir = _humidity_direction(humidity_trend_pct)
    rain_band = _rain_band(rain_high_mm)

    if rain_band == "high" and (temp_dir == "falling" or hum_dir == "rising"):
        return {"day_type": DAY_TYPE_RAINY,
                "reason": "Heavy rain expected, with temperature falling and/or humidity rising — a system is moving in."}

    if rain_band == "low" and hum_dir != "rising" and temp_dir != "falling":
        return {"day_type": DAY_TYPE_SUNNY,
                "reason": "Little rain expected and humidity isn't building — clear and dry."}

    if temp_dir == "rising" and hum_dir == "rising":
        return {"day_type": DAY_TYPE_STORM_RISK,
                "reason": "Temperature and humidity both climbing — classic build-up for an afternoon thunderstorm."}

    if hum_dir == "rising" and rain_band != "high":
        return {"day_type": DAY_TYPE_OVERCAST,
                "reason": "Humidity building without much rain materializing yet — cloudy skies likely."}

    return {"day_type": DAY_TYPE_MILD,
            "reason": "No strong trend in temperature or humidity — an unremarkable day."}
