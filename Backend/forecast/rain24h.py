"""
forecast.rain24h
──────────────────
Everything the 24-hour-total rain model needs that production doesn't
already compute: per-district climate zone / peak-season lookups, the
apparent-temperature formula, the 28-feature engineering pipeline (must
exactly mirror extra/output/24_hour_rainfall/data_prep.py's FEATURE_COLS),
and the day-type classifier.

WHY THE 28-FEATURE MODEL, NOT THE 35-FEATURE ONE: a wider version of this
model (35 features — dew point, pressure, wind direction, vapour pressure
deficit, soil moisture) scored marginally better offline (R²=0.292 vs
0.278), but SoilMoisture_0_7cm has no live source — WeatherAPI doesn't
provide it and there's no defensible way to derive it from temperature/
humidity/rain the way apparent temperature can be derived. Serving a model
on a silently-approximated input feature is a real production risk; the
28<->35 feature gap was also already shown (via two full training runs) to
be within normal run-to-run noise, not a proven real difference. So this
uses the 28-feature model, which needs nothing WeatherAPI doesn't already
provide either directly or via a validated derived formula below.

APPARENT TEMPERATURE: WeatherAPI's hourly forecast/history objects were
never confirmed to include feelslike_c the way current.json does, so this
computes it from temperature + humidity + wind speed using the Australian
Bureau of Meteorology's formula, bias-corrected against the real training
data (validated on 5,000 real samples: raw formula MAE=0.986°C with a
consistent -0.986°C bias; bias-corrected MAE=0.476°C, ~zero bias) — well
inside the deployed temperature model's own MAE (0.719°C).

CLIMATE ZONE / PEAK SEASON: both extracted directly from the real training
data (sri_lanka_labeled_extended.parquet), not guessed. Peak season turned
out to be a clean function of (climate zone, month) — verified per-district,
not assumed.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# ──────────────────────────────────────────────────────────────────────────
# Static lookups — extracted directly from the real training dataset
# ──────────────────────────────────────────────────────────────────────────

DISTRICT_CLIMATE_ZONE: Dict[str, int] = {
    "Colombo": 1, "Galle": 1, "Gampaha": 1, "Kalutara": 1, "Matara": 1,
    "Ampara": 2, "Anuradhapura": 2, "Batticaloa": 2, "Hambantota": 2,
    "Jaffna": 2, "Kilinochchi": 2, "Mannar": 2, "Monaragala": 2,
    "Polonnaruwa": 2, "Puttalam": 2, "Trincomalee": 2, "Vavuniya": 2,
    "Mullaitivu": 2,
    "Kandy": 3, "Kegalle": 3, "Kurunegala": 3, "Matale": 3, "Ratnapura": 3,
    "Badulla": 4, "NuwaraEliya": 4,
}

# Verified per-district against the real dataset: peak season is a clean
# function of (climate zone, month), not a fixed calendar range.
#   Zone 1 (wet/coastal-west): Dec-Mar (that coast's dry season)
#   Zone 2 (dry zone): May-Sep (that region's dry season)
#   Zone 3 (intermediate): Jan/Feb + Jul/Aug + Dec (blend of both)
#   Zone 4 (hill country): Jan-Apr
ZONE_PEAK_MONTHS: Dict[int, set] = {
    1: {1, 2, 3, 12},
    2: {5, 6, 7, 8, 9},
    3: {1, 2, 7, 8, 12},
    4: {1, 2, 3, 4},
}

CLIMATE_ZONES: List[int] = [1, 2, 3, 4]

# Bias correction for the AU Bureau of Meteorology apparent-temperature
# formula, fit against 5,000 real samples from the training dataset (see
# module docstring). A single additive constant, not a full regression —
# the raw formula's error was already ~unbiased in shape, just offset.
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
    """AU Bureau of Meteorology formula, bias-corrected (see module
    docstring). Vectorized — accepts scalars or numpy arrays/Series."""
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
    """frame: the same 168-row context DataFrame WeatherRepository.
    fetch_context_window() already produces for the deployed temp/humidity
    model (columns: datetime, Temperature_C, Precipitation_mm, Humidity_%,
    CloudCover_%, WindSpeed_kmh, WindGusts_kmh, DaylightScore, Hour, Month).
    Returns the 28 FEATURE_COLS, in order, ready to scale + feed the model.

    Must be called on one CONTIGUOUS 168-hour window for a single district —
    lags/rolling/trend windows must not cross a gap."""
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


# ──────────────────────────────────────────────────────────────────────────
# Day-type classifier — temp trend + humidity trend + rain range, not rain
# amount alone. Rules as specified:
#
#   Rainy               : temp falling, humidity rising, rain HIGH
#   Sunny / clear        : temp stable-or-rising, humidity falling/low, rain LOW
#   Overcast             : temp stable, humidity high/rising, rain LOW-MODERATE
#   Hot-humid/storm-risk : temp rising, humidity rising, rain LOW-TO-MODERATE (not yet high)
#   Mild                 : everything else (nothing distinctive)
# ──────────────────────────────────────────────────────────────────────────

DAY_TYPE_RAINY = "RAINY"
DAY_TYPE_SUNNY = "SUNNY"
DAY_TYPE_OVERCAST = "OVERCAST"
DAY_TYPE_STORM_RISK = "HOT_HUMID_STORM_RISK"
DAY_TYPE_MILD = "MILD"

# Trend thresholds: how much change over 24h counts as "rising"/"falling"
# vs "stable". +-0.5C / +-3% are small but real signals at this timescale —
# tight enough to catch a genuine trend, loose enough that measurement
# noise doesn't flip the label hour to hour.
TEMP_TREND_THRESHOLD_C = 0.5
HUMIDITY_TREND_THRESHOLD_PCT = 3.0

# Rain range thresholds (mm, 24h TOTAL — not hourly). Calibrated against the
# real 24h-rolling-total distribution across the whole training dataset
# (median 1.9mm, 75th pct 6.9mm, 90th pct 16.2mm) — an earlier version of
# this reused hourly_advisory's 3mm/10mm hourly cutoffs directly for a daily
# TOTAL, which was wrong: daily totals blow past 3mm on ~41% of days, so
# almost every rainy day landed in the "high" band and only RAINY (the one
# category requiring "high") could ever match, starving every other
# category. LOW_MAX≈48th percentile, MODERATE_MAX≈78th percentile.
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
    """The day's rain HIGH bound (the cautious end of the range) drives the
    rain band, consistent with hourly_advisory's own "react to the high
    end" logic. temp_trend_c/humidity_trend_pct are the SAME Temp_Trend_24h/
    Humidity_Trend_24h features the model itself already uses — this reuses
    real signal already computed, not a second set of numbers.

    Matching is deliberately OR-based within each rule, not a strict AND of
    all three signals — an earlier AND-only version, checked against the
    real training data, put 67% of all real days into MILD (the fallback)
    because requiring temp direction AND humidity direction AND rain band
    to all align simultaneously is a narrow intersection real weather
    rarely hits exactly. This version, verified the same way against the
    same real data, produces a genuinely differentiated split (MILD 34%,
    SUNNY 34%, OVERCAST 20%, RAINY 10%, STORM_RISK 2%)."""
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
