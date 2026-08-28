from __future__ import annotations

import numpy as np
import pandas as pd

from config import (
    CLIMATE_ZONES, DATA_PATH, DISTRICT_SHEETS, INPUT_WINDOW, RAIN_ZERO_FLOOR_MM,
    TARGET_HORIZON, TRAIN_FRACTION, VAL_FRACTION, WINDOW_STRIDE,
)

RAW_COLS = [
    "Date", "Hour", "Month", "ClimateZone", "IsPeakSeason", "DaylightScore",
    "Temperature_C", "ApparentTemp_C", "Precipitation_mm", "Humidity_%",
    "WindSpeed_kmh", "WindGusts_kmh", "CloudCover_%",
    "DewPoint_C", "Pressure_hPa", "WindDirection_deg",
    "VapourPressureDeficit_kPa", "SoilMoisture_0_7cm",
]

FEATURE_COLS = [
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
    "DewPoint_C", "Pressure_hPa", "Pressure_Change_3h",
    "WindDir_sin", "WindDir_cos",
    "VapourPressureDeficit_kPa", "SoilMoisture_0_7cm",
]
N_FEATURES = len(FEATURE_COLS)

def load_all_districts(path: str = DATA_PATH) -> dict[str, pd.DataFrame]:
    print(f"Loading {path} ...")
    full = pd.read_parquet(path, columns=list(dict.fromkeys(RAW_COLS + ["District"])))
    out = {}
    for sheet in DISTRICT_SHEETS:
        df = full[full["District"] == sheet][RAW_COLS].reset_index(drop=True)
        df["observed_at"] = pd.to_datetime(df["Date"]) + pd.to_timedelta(df["Hour"], unit="h")
        df = df.sort_values("observed_at").reset_index(drop=True)
        out[sheet] = df
        print(f"  {sheet}: {len(df)} rows, {df['observed_at'].min()} to {df['observed_at'].max()}")
    total = sum(len(v) for v in out.values())
    print(f"Loaded {len(out)} districts, {total:,} total rows.")
    return out

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["Hour_sin"] = np.sin(2 * np.pi * df["Hour"] / 24.0)
    df["Hour_cos"] = np.cos(2 * np.pi * df["Hour"] / 24.0)
    df["Month_sin"] = np.sin(2 * np.pi * df["Month"] / 12.0)
    df["Month_cos"] = np.cos(2 * np.pi * df["Month"] / 12.0)
    df["Temp_Change_3h"] = df["Temperature_C"].diff(periods=3).fillna(0.0)

    df["ApparentTemp_Diff"] = df["ApparentTemp_C"] - df["Temperature_C"]

    for zone in CLIMATE_ZONES:
        df[f"ClimateZone_{zone}"] = (df["ClimateZone"] == zone).astype(np.float32)

    df["Rain_lag_1h"] = df["Precipitation_mm"].shift(1).fillna(0.0)
    df["Rain_lag_3h"] = df["Precipitation_mm"].shift(3).fillna(0.0)
    df["Rain_lag_6h"] = df["Precipitation_mm"].shift(6).fillna(0.0)
    df["Rain_rolling_6h"] = df["Precipitation_mm"].rolling(6, min_periods=1).sum()
    df["Rain_rolling_24h"] = df["Precipitation_mm"].rolling(24, min_periods=1).sum()
    df["Rain_rolling_48h"] = df["Precipitation_mm"].rolling(48, min_periods=1).sum()
    df["Rain_rolling_72h"] = df["Precipitation_mm"].rolling(72, min_periods=1).sum()

    df["Temp_Trend_24h"] = df["Temperature_C"].diff(periods=24).fillna(0.0)
    df["Humidity_Trend_24h"] = df["Humidity_%"].diff(periods=24).fillna(0.0)

    df["Pressure_Change_3h"] = df["Pressure_hPa"].diff(periods=3).fillna(0.0)
    wind_rad = np.deg2rad(df["WindDirection_deg"])
    df["WindDir_sin"] = np.sin(wind_rad)
    df["WindDir_cos"] = np.cos(wind_rad)

    all_cols = list(dict.fromkeys(FEATURE_COLS + ["Precipitation_mm"]))
    return df[all_cols + ["observed_at"]]

def _contiguous_hourly_segments(df: pd.DataFrame) -> list[pd.DataFrame]:
    gaps = df["observed_at"].diff() != pd.Timedelta(hours=1)
    gaps.iloc[0] = True
    segment_id = gaps.cumsum()
    return [g.reset_index(drop=True) for _, g in df.groupby(segment_id)]

def build_split_windows(
    district_frames: dict[str, pd.DataFrame],
    input_window: int = INPUT_WINDOW,
    horizon: int = TARGET_HORIZON,
    stride: int = WINDOW_STRIDE,
) -> dict[str, dict]:
    need = input_window + horizon

    segments_by_district: dict[str, list[tuple[np.ndarray, np.ndarray, np.ndarray]]] = {}
    locations: list[tuple[str, int, int, np.datetime64]] = []

    for district, raw in district_frames.items():
        segments_by_district[district] = []
        district_window_count = 0
        for seg_idx, segment in enumerate(_contiguous_hourly_segments(raw)):
            if len(segment) < need:
                continue
            engineered = engineer_features(segment)
            feats = engineered[FEATURE_COLS].values.astype(np.float32)
            rain = engineered["Precipitation_mm"].values.astype(np.float32)
            times = engineered["observed_at"].values
            segments_by_district[district].append((feats, rain, times))

            last_start = len(segment) - need
            for start in range(0, last_start + 1, stride):
                ctx_end = start + input_window
                locations.append((district, seg_idx, start, times[ctx_end - 1]))
                district_window_count += 1
        print(f"  {district}: {district_window_count} windows (stride={stride})")

    n_total = len(locations)
    print(f"Built {n_total:,} window locations, {input_window}h context -> 24h-ahead rain "
          f"TOTAL ({N_FEATURES} features; no window data copied yet).")

    locations.sort(key=lambda loc: loc[3])

    n_train = int(n_total * TRAIN_FRACTION)
    n_val = int(n_total * VAL_FRACTION)
    n_test = n_total - n_train - n_val
    split_sizes = {"train": n_train, "val": n_val, "test": n_test}

    result = {
        name: {
            "X": np.empty((size, input_window, N_FEATURES), dtype=np.float32),
            "y_total": np.empty((size,), dtype=np.float32),
            "y_occurred": np.empty((size,), dtype=np.float32),
            "dt": [None] * size,
            "district": [None] * size,
        }
        for name, size in split_sizes.items()
    }

    cursor = {"train": 0, "val": 0, "test": 0}
    boundaries = [("train", n_train), ("val", n_val), ("test", n_test)]

    pos = 0
    for name, size in boundaries:
        for _ in range(size):
            district, seg_idx, start, origin_time = locations[pos]
            feats, rain, times = segments_by_district[district][seg_idx]
            ctx_end = start + input_window
            tgt_end = ctx_end + horizon
            total_rain = float(rain[ctx_end:tgt_end].sum())

            i = cursor[name]
            result[name]["X"][i] = feats[start:ctx_end]
            result[name]["y_total"][i] = total_rain
            result[name]["y_occurred"][i] = 1.0 if result[name]["y_total"][i] > RAIN_ZERO_FLOOR_MM else 0.0
            result[name]["dt"][i] = origin_time
            result[name]["district"][i] = district
            cursor[name] += 1
            pos += 1

    for name in ("train", "val", "test"):
        dt = result[name]["dt"]
        occ_rate = result[name]["y_occurred"].mean() if len(dt) else 0.0
        print(f"  {name}: {len(dt):,} windows ({dt[0] if dt else '-'} to {dt[-1] if dt else '-'}), "
              f"{occ_rate:.1%} have measurable rain in the next 24h")

    return result
