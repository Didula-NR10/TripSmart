"""
training.dataset_extended
─────────────────────────────
Same windowing discipline as dataset.py — per district, gap-aware, a window
never spans a real data gap or a district boundary — but running the
EXTENDED 22-feature pipeline (extended_features.py) instead of the
production 12-feature contract. Kept as a separate module (reusing
dataset.py's gap-detection helper) so the production windowing path stays
visibly untouched by this experimental, wider one.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from training.config import INPUT_WINDOW, TARGET_HORIZON, TRAIN_FRACTION, VAL_FRACTION
from training.dataset import _contiguous_hourly_segments
from training.extended_features import EXTENDED_FEATURE_COLS, engineer_extended_features

log = logging.getLogger("trip_smart.training.dataset_extended")

TARGET_COLS = ["Temperature_C", "Precipitation_mm", "Humidity_%"]


def build_extended_windows(
    district_frames: dict[str, pd.DataFrame],
    input_window: int = INPUT_WINDOW,
    horizon: int = TARGET_HORIZON,
) -> tuple[np.ndarray, np.ndarray, list[pd.Timestamp], list[str]]:
    X_list, y_list, dt_list, dist_list = [], [], [], []
    need = input_window + horizon

    for district, raw in district_frames.items():
        raw = raw.sort_values("observed_at").reset_index(drop=True)
        usable = 0
        for segment in _contiguous_hourly_segments(raw):
            if len(segment) < need:
                continue

            segment = segment.copy()
            segment["Hour"] = segment["observed_at"].dt.hour
            segment["Month"] = segment["observed_at"].dt.month
            engineered = engineer_extended_features(segment)
            feats = engineered[EXTENDED_FEATURE_COLS].values.astype(np.float32)
            targs = engineered[TARGET_COLS].values.astype(np.float32)

            last_start = len(segment) - need
            for start in range(0, last_start + 1):
                ctx_end = start + input_window
                tgt_end = ctx_end + horizon
                X_list.append(feats[start:ctx_end])
                y_list.append(targs[ctx_end:tgt_end])
                dt_list.append(segment["observed_at"].iloc[ctx_end - 1])
                dist_list.append(district)
                usable += 1

        log.info("%s: %d windows.", district, usable)

    if not X_list:
        raise ValueError(f"No district has {need} contiguous hourly observations yet.")

    return np.stack(X_list), np.stack(y_list), dt_list, dist_list


def chronological_split(X, y, dt_list, dist_list) -> dict[str, dict]:
    order = np.argsort(dt_list)
    X, y = X[order], y[order]
    dt_sorted = [dt_list[i] for i in order]
    dist_sorted = [dist_list[i] for i in order]

    n = len(X)
    n_train = int(n * TRAIN_FRACTION)
    n_val = int(n * VAL_FRACTION)

    splits = {"train": slice(0, n_train), "val": slice(n_train, n_train + n_val), "holdout": slice(n_train + n_val, n)}
    result = {}
    for name, sl in splits.items():
        result[name] = {"X": X[sl], "y": y[sl], "dt": dt_sorted[sl], "district": dist_sorted[sl]}
        log.info("%s: %d windows", name, sl.stop - sl.start)
    return result
