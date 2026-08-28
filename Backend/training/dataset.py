from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from forecast.utils import FINAL_FEATURE_COLS, TARGET_COLS, TARGET_INDICES, engineer_features
from training.config import INPUT_WINDOW, TARGET_HORIZON, TRAIN_FRACTION, VAL_FRACTION

log = logging.getLogger("trip_smart.training.dataset")

def _contiguous_hourly_segments(df: pd.DataFrame) -> list[pd.DataFrame]:
    gaps = df["observed_at"].diff() != pd.Timedelta(hours=1)
    gaps.iloc[0] = True
    segment_id = gaps.cumsum()
    return [g.reset_index(drop=True) for _, g in df.groupby(segment_id)]

def build_windows(
    district_frames: dict[str, pd.DataFrame],
    input_window: int = INPUT_WINDOW,
    horizon: int = TARGET_HORIZON,
) -> tuple[np.ndarray, np.ndarray, list[pd.Timestamp], list[str]]:
    X_list, y_list, dt_list, dist_list = [], [], [], []
    need = input_window + horizon

    for district, raw in district_frames.items():
        raw = raw.sort_values("observed_at").reset_index(drop=True)
        total_hours = len(raw)

        usable = 0
        for segment in _contiguous_hourly_segments(raw):
            if len(segment) < need:
                continue

            segment = segment.copy()
            segment["Hour"] = segment["observed_at"].dt.hour
            segment["Month"] = segment["observed_at"].dt.month
            engineered = engineer_features(segment)
            feats = engineered[FINAL_FEATURE_COLS].values.astype(np.float32)
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

        log.info("%s: %d/%d hours usable -> %d windows.", district, total_hours, total_hours, usable)

    if not X_list:
        raise ValueError(
            f"No district has {need} contiguous hourly observations yet "
            f"({input_window}h context + {horizon}h horizon) — nothing to train on."
        )

    return np.stack(X_list), np.stack(y_list), dt_list, dist_list

def chronological_split(
    X: np.ndarray, y: np.ndarray, dt_list: list, dist_list: list[str],
) -> dict[str, dict]:
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
        "holdout": slice(n_train + n_val, n),
    }
    result = {}
    for name, sl in splits.items():
        result[name] = {
            "X": X[sl], "y": y[sl],
            "dt": dt_sorted[sl], "district": dist_sorted[sl],
        }
        log.info("%s: %d windows%s", name, sl.stop - sl.start,
                  f" ({result[name]['dt'][0]} to {result[name]['dt'][-1]})" if sl.stop > sl.start else "")
    return result

def scale_features(X: np.ndarray, scaler) -> np.ndarray:
    n, w, f = X.shape
    return scaler.transform(X.reshape(-1, f)).reshape(n, w, f).astype(np.float32)

def scale_targets(y: np.ndarray, scaler) -> np.ndarray:
    n, h, t = y.shape
    placeholder = np.zeros((n * h, len(FINAL_FEATURE_COLS)), dtype=np.float32)
    for out_idx, feat_idx in enumerate(TARGET_INDICES):
        placeholder[:, feat_idx] = y.reshape(n * h, t)[:, out_idx]
    scaled = scaler.transform(placeholder)
    return scaled[:, TARGET_INDICES].reshape(n, h, t).astype(np.float32)
