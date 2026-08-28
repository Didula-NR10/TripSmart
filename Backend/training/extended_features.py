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
    base = engineer_features(df)

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
