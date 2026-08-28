from __future__ import annotations

import numpy as np
import pandas as pd

def build_supervised_table(
    df: pd.DataFrame,
    tabular_feature_cols: list[str],
    target_cols: list[str],
    horizon: int = 24,
) -> pd.DataFrame:
    frames = []
    for district, g in df.groupby("district", sort=False):
        g = g.sort_values("datetime").reset_index(drop=True)
        n = len(g)
        max_origin = n - horizon - 1
        if max_origin < 0:
            print(f"[features_gbm] {district}: only {n} hours, need at least {horizon + 1} — skipped.")
            continue

        origin_indices = np.arange(0, max_origin + 1)
        h_arr = np.tile(np.arange(1, horizon + 1), len(origin_indices))
        origin_repeated = np.repeat(origin_indices, horizon)
        target_indices = origin_repeated + h_arr

        table = g.loc[origin_repeated, tabular_feature_cols].reset_index(drop=True)
        table["lead_hour"] = h_arr
        table["lead_hour_sin"] = np.sin(2 * np.pi * h_arr / 24.0)
        table["lead_hour_cos"] = np.cos(2 * np.pi * h_arr / 24.0)

        target_dt = g.loc[target_indices, "datetime"].reset_index(drop=True)
        target_hour = target_dt.dt.hour.values
        target_month = target_dt.dt.month.values
        table["target_hour_sin"] = np.sin(2 * np.pi * target_hour / 24.0)
        table["target_hour_cos"] = np.cos(2 * np.pi * target_hour / 24.0)
        table["target_month_sin"] = np.sin(2 * np.pi * target_month / 12.0)
        table["target_month_cos"] = np.cos(2 * np.pi * target_month / 12.0)

        table["origin_datetime"] = g.loc[origin_repeated, "datetime"].values
        table["district"] = district

        for tcol in target_cols:
            table[f"target_{tcol}"] = g.loc[target_indices, tcol].reset_index(drop=True).values

        frames.append(table)

    if not frames:
        raise ValueError(f"No district had at least {horizon + 1} hours of data.")

    result = pd.concat(frames, ignore_index=True)
    print(f"[features_gbm] Built supervised table: {len(result)} rows "
          f"({result['district'].nunique()} district(s), {horizon} lead hours each).")
    return result

def model_feature_cols(tabular_feature_cols: list[str]) -> list[str]:
    return tabular_feature_cols + [
        "lead_hour", "lead_hour_sin", "lead_hour_cos",
        "target_hour_sin", "target_hour_cos", "target_month_sin", "target_month_cos",
    ]

def chronological_split_table(table: pd.DataFrame):
    from config import TEST_FRACTION, TRAIN_FRACTION, VAL_FRACTION

    origins = table[["district", "origin_datetime"]].drop_duplicates().sort_values("origin_datetime")
    n = len(origins)
    n_train = int(n * TRAIN_FRACTION)
    n_val = int(n * VAL_FRACTION)

    train_origins = origins.iloc[:n_train]
    val_origins = origins.iloc[n_train:n_train + n_val]
    test_origins = origins.iloc[n_train + n_val:]

    def _subset(origin_slice: pd.DataFrame) -> pd.DataFrame:
        key = origin_slice.set_index(["district", "origin_datetime"]).index
        return table.set_index(["district", "origin_datetime"], drop=False).loc[
            table.set_index(["district", "origin_datetime"]).index.isin(key)
        ].reset_index(drop=True)

    splits = {
        "train": _subset(train_origins),
        "val": _subset(val_origins),
        "test": _subset(test_origins),
    }
    for name, s in splits.items():
        if len(s):
            print(f"[features_gbm] {name}: {s['origin_datetime'].nunique()} origins, "
                  f"{len(s)} rows, {s['origin_datetime'].min()} to {s['origin_datetime'].max()}")
        else:
            print(f"[features_gbm] {name}: 0 rows")
    return splits

def reshape_to_3d(table: pd.DataFrame, pred_cols: dict[str, str], target_cols: list[str], horizon: int = 24):
    table = table.sort_values(["district", "origin_datetime", "lead_hour"])
    origins = table[["district", "origin_datetime"]].drop_duplicates()
    n_origins = len(origins)
    n_targets = len(target_cols)

    y_true = np.full((n_origins, horizon, n_targets), np.nan, dtype=np.float32)
    y_pred = np.full((n_origins, horizon, n_targets), np.nan, dtype=np.float32)

    grouped = table.groupby(["district", "origin_datetime"], sort=True)
    for i, (_, g) in enumerate(grouped):
        g = g.sort_values("lead_hour")
        for t, tcol in enumerate(target_cols):
            y_true[i, :, t] = g[f"target_{tcol}"].values
            y_pred[i, :, t] = g[pred_cols[tcol]].values

    return y_true, y_pred
