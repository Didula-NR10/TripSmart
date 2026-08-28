from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from config import (
    BASE_FEATURE_COLS,
    EXTENDED_FEATURE_COLS,
    INPUT_WINDOW,
    MAX_RADIATION_WM2,
    OPTIONAL_RAW_COLUMNS,
    RAW_COLUMN_ALIASES,
    REQUIRED_RAW_COLUMNS,
    TARGET_COLS,
    TARGET_HORIZON,
    TEST_FRACTION,
    TRAIN_FRACTION,
    VAL_FRACTION,
)

def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())

def resolve_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized_lookup = {_normalize(c): c for c in df.columns}

    rename_map: dict[str, str] = {}
    found: set[str] = set()
    for canonical, aliases in RAW_COLUMN_ALIASES.items():
        for alias in [canonical] + aliases:
            key = _normalize(alias)
            if key in normalized_lookup:
                rename_map[normalized_lookup[key]] = canonical
                found.add(canonical)
                break

    missing_required = [c for c in REQUIRED_RAW_COLUMNS if c not in found]
    if missing_required:
        raise ValueError(
            "Could not find required column(s) in the source data: "
            f"{missing_required}.\n"
            f"Columns present in the file: {list(df.columns)}\n"
            f"Add an alias for the missing field(s) to RAW_COLUMN_ALIASES in "
            f"common/config.py, or rename the column in the source file to "
            f"one of the recognized names."
        )

    df = df.rename(columns=rename_map)
    missing_optional = [c for c in OPTIONAL_RAW_COLUMNS if c not in found]
    if missing_optional:
        print(f"[data_prep] Optional columns not found (fine, features "
              f"depending on them are skipped): {missing_optional}")
    return df

def load_raw_table(path: str | Path, sheet_name: Optional[str] = None) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path, sheet_name=sheet_name or 0)
    elif path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}. Use .xlsx or .csv.")

    df = resolve_columns(df)
    df["datetime"] = pd.to_datetime(df["datetime"])

    if "district" not in df.columns:
        df["district"] = "default"
        print("[data_prep] No district/location column found — treating the "
              "whole file as one continuous series under district='default'. "
              "If your data actually covers multiple districts concatenated "
              "together, add a district column or windows will incorrectly "
              "span district boundaries.")

    sort_cols = ["district", "datetime"]
    df = df.sort_values(sort_cols).reset_index(drop=True)

    dupes = df.duplicated(subset=["district", "datetime"]).sum()
    if dupes:
        print(f"[data_prep] {dupes} duplicate (district, datetime) rows found — keeping the first.")
        df = df.drop_duplicates(subset=["district", "datetime"], keep="first").reset_index(drop=True)

    return df

def _fill_gaps_per_district(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for district, g in df.groupby("district", sort=False):
        g = g.set_index("datetime").sort_index()
        full_range = pd.date_range(g.index.min(), g.index.max(), freq="h")
        missing = full_range.difference(g.index)
        if len(missing):
            print(f"[data_prep] {district}: {len(missing)} missing hourly rows "
                  f"out of {len(full_range)} — filled via ffill/bfill.")
        g = g.reindex(full_range)
        g = g.ffill().bfill()
        g["district"] = district
        g.index.name = "datetime"
        out.append(g.reset_index())
    return pd.concat(out, ignore_index=True)

def engineer_features(df: pd.DataFrame, extended: bool = False) -> pd.DataFrame:
    df = _fill_gaps_per_district(df)

    out_frames = []
    for district, g in df.groupby("district", sort=False):
        g = g.sort_values("datetime").reset_index(drop=True)

        g["Hour"] = g["datetime"].dt.hour
        g["Month"] = g["datetime"].dt.month
        g["DaylightScore"] = (g["radiation"] / MAX_RADIATION_WM2).clip(0.0, 1.0)

        g["Hour_sin"] = np.sin(2 * np.pi * g["Hour"] / 24.0)
        g["Hour_cos"] = np.cos(2 * np.pi * g["Hour"] / 24.0)
        g["Month_sin"] = np.sin(2 * np.pi * g["Month"] / 12.0)
        g["Month_cos"] = np.cos(2 * np.pi * g["Month"] / 12.0)
        g["Temp_Change_3h"] = g["Temperature_C"].diff(periods=3).fillna(0.0)

        if extended:
            g["Temp_lag_24h"] = g["Temperature_C"].shift(24)
            g["Temp_lag_168h"] = g["Temperature_C"].shift(168)
            g["Humidity_lag_24h"] = g["Humidity_%"].shift(24)
            g["Humidity_lag_168h"] = g["Humidity_%"].shift(168)
            g["Rain_sum_24h"] = g["Precipitation_mm"].rolling(24, min_periods=1).sum()
            g["Rain_sum_72h"] = g["Precipitation_mm"].rolling(72, min_periods=1).sum()
            g["Temp_roll_mean_24h"] = g["Temperature_C"].rolling(24, min_periods=1).mean()
            g["Temp_roll_std_24h"] = g["Temperature_C"].rolling(24, min_periods=1).std().fillna(0.0)
            g["Humidity_roll_mean_24h"] = g["Humidity_%"].rolling(24, min_periods=1).mean()
            g["CloudCover_roll_mean_24h"] = g["CloudCover_%"].rolling(24, min_periods=1).mean()

            for lag_col in ("Temp_lag_24h", "Temp_lag_168h", "Humidity_lag_24h", "Humidity_lag_168h"):
                g[lag_col] = g[lag_col].bfill()

            if "Pressure_hPa" not in g.columns:
                g["Pressure_hPa"] = np.nan
            if "DewPoint_C" not in g.columns:
                g["DewPoint_C"] = np.nan

        out_frames.append(g)

    result = pd.concat(out_frames, ignore_index=True)
    result = result.sort_values(["district", "datetime"]).reset_index(drop=True)

    if extended:
        for col in ("Pressure_hPa", "DewPoint_C"):
            if result[col].isnull().all():
                result = result.drop(columns=[col])
                print(f"[data_prep] '{col}' not present in source data — dropped from extended features.")
            else:
                result[col] = result[col].ffill().bfill()

    return result

def feature_columns(extended: bool = False, df: Optional[pd.DataFrame] = None) -> list[str]:
    cols = list(BASE_FEATURE_COLS)
    if extended:
        extra = list(EXTENDED_FEATURE_COLS)
        if df is not None:
            extra = [c for c in extra if c in df.columns]
        cols = cols + extra
    return cols

def make_windows(
    df: pd.DataFrame,
    feature_cols: list[str],
    input_window: int = INPUT_WINDOW,
    horizon: int = TARGET_HORIZON,
    target_cols: list[str] = TARGET_COLS,
):
    X_list, y_list, dt_list, dist_list = [], [], [], []

    for district, g in df.groupby("district", sort=False):
        g = g.sort_values("datetime").reset_index(drop=True)
        feats = g[feature_cols].values.astype(np.float32)
        targs = g[target_cols].values.astype(np.float32)
        n = len(g)

        last_start = n - input_window - horizon
        if last_start < 0:
            print(f"[data_prep] {district}: only {n} hours, need at least "
                  f"{input_window + horizon} — skipped.")
            continue

        for start in range(0, last_start + 1):
            end_ctx = start + input_window
            end_tgt = end_ctx + horizon
            X_list.append(feats[start:end_ctx])
            y_list.append(targs[end_ctx:end_tgt])
            dt_list.append(g["datetime"].iloc[end_ctx - 1])
            dist_list.append(district)

    if not X_list:
        raise ValueError(
            "No windows could be built from any district — the data is "
            f"shorter than input_window + horizon = {input_window + horizon} hours."
        )

    X = np.stack(X_list)
    y = np.stack(y_list)
    print(f"[data_prep] Built {len(X)} windows across {df['district'].nunique()} district(s) "
          f"({X.shape[1]}h context, {y.shape[1]}h horizon, {X.shape[2]} features).")
    return X, y, dt_list, dist_list

def chronological_split(X, y, dt_list, dist_list):
    order = np.argsort(dt_list)
    X, y = X[order], y[order]
    dt_sorted = [dt_list[i] for i in order]
    dist_sorted = [dist_list[i] for i in order]

    n = len(X)
    n_train = int(n * TRAIN_FRACTION)
    n_val = int(n * VAL_FRACTION)

    splits = {
        "train": slice(0, n_train),
        "val": slice(n_train, n_train + n_val),
        "test": slice(n_train + n_val, n),
    }
    result = {}
    for name, sl in splits.items():
        result[name] = {
            "X": X[sl], "y": y[sl],
            "dt": dt_sorted[sl], "district": dist_sorted[sl],
        }
        if len(result[name]["dt"]):
            print(f"[data_prep] {name}: {sl.stop - sl.start} windows, "
                  f"{result[name]['dt'][0]} to {result[name]['dt'][-1]}")
        else:
            print(f"[data_prep] {name}: 0 windows")
    return result
