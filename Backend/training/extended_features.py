"""
training.extended_features
──────────────────────────────
Item 3 of the improvement plan: real new signal, not just more of what the
model already has. Adds 10 columns on top of the production 12-feature
contract (forecast/utils.py's FINAL_FEATURE_COLS, left completely
untouched — this is a SEPARATE, wider contract for an experimental model,
not a change to what's deployed):

  - DewPoint_C, Pressure_hPa       — raw
  - Pressure_Change_3h             — trend matters more than the raw value,
                                      same logic as the existing Temp_Change_3h
  - WindDir_sin, WindDir_cos       — circular encoding (wind direction is
                                      exactly the kind of 0°/360°-wraparound
                                      quantity the existing Hour/Month
                                      cyclical encoding already handles)
  - Rain_lag_1h/3h/6h              — storm persistence (rain tends to cluster)
  - Rain_rolling_6h, Rain_rolling_24h — recent wet-spell context

Why these specifically, not an arbitrary larger set: each one is a concrete,
named meteorological mechanism for rain (falling pressure precedes storms;
dew-point gap measures saturation; wind direction indicates which air mass —
moist monsoon vs dry interior — is arriving; rain persistence and recent
wetness are the closest thing to genuine short-term memory a point-based
model can have). Every feature engineered here is defensible on its own
terms, not just "more numbers."
"""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from forecast.utils import FINAL_FEATURE_COLS, engineer_features

NEW_FEATURE_COLS: List[str] = [
    "DewPoint_C",
    "Pressure_hPa",
    "Pressure_Change_3h",
    "WindDir_sin",
    "WindDir_cos",
    "Rain_lag_1h",
    "Rain_lag_3h",
    "Rain_lag_6h",
    "Rain_rolling_6h",
    "Rain_rolling_24h",
]

EXTENDED_FEATURE_COLS: List[str] = FINAL_FEATURE_COLS + NEW_FEATURE_COLS


def engineer_extended_features(df: pd.DataFrame) -> pd.DataFrame:
    """df must already have the base 7 raw columns (see forecast.utils) PLUS
    DewPoint_C, Pressure_hPa, WindDirection_deg, Hour, Month. Must be called
    on one CONTIGUOUS hourly segment of one district at a time — lags and
    rolling windows must never cross a real data gap or a district
    boundary, same discipline dataset.py already applies for the base 12."""
    base = engineer_features(df)  # the untouched, production 12-column contract

    df = df.copy()
    df["Pressure_Change_3h"] = df["Pressure_hPa"].diff(periods=3).fillna(0.0)

    wind_rad = np.deg2rad(df["WindDirection_deg"])
    df["WindDir_sin"] = np.sin(wind_rad)
    df["WindDir_cos"] = np.cos(wind_rad)

    df["Rain_lag_1h"] = df["Precipitation_mm"].shift(1).fillna(0.0)
    df["Rain_lag_3h"] = df["Precipitation_mm"].shift(3).fillna(0.0)
    df["Rain_lag_6h"] = df["Precipitation_mm"].shift(6).fillna(0.0)
    df["Rain_rolling_6h"] = df["Precipitation_mm"].rolling(6, min_periods=1).sum()
    df["Rain_rolling_24h"] = df["Precipitation_mm"].rolling(24, min_periods=1).sum()

    extended = pd.concat([base.reset_index(drop=True), df[NEW_FEATURE_COLS].reset_index(drop=True)], axis=1)
    return extended[EXTENDED_FEATURE_COLS]
