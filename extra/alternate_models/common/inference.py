"""
alternate_models/common/inference.py
───────────────────────────────────────
Loads whichever kind of trained model lives in a given artifacts/ folder
(a deep Keras model, or the LightGBM 3-model trio) and predicts the next
24 hours from a live context window, uniformly — run_forecast.py and
compare_with_openmeteo.py don't need to know which architecture they're
talking to.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import data_prep
import scaling
from config import TARGET_COLS, TARGET_HORIZON


def load_trained_model(model_dir: str | Path) -> dict[str, Any]:
    model_dir = Path(model_dir)
    artifacts = model_dir / "artifacts"
    if not artifacts.exists():
        raise FileNotFoundError(f"No artifacts/ folder in {model_dir} — train the model first.")

    if (artifacts / "model.keras").exists():
        import joblib
        import tensorflow as tf

        model = tf.keras.models.load_model(artifacts / "model.keras")
        scaler = joblib.load(artifacts / "scaler.pkl")
        with open(artifacts / "feature_cols.json") as f:
            feature_cols = json.load(f)
        return {"kind": "deep", "model": model, "scaler": scaler, "feature_cols": feature_cols,
                "name": model_dir.name}

    if (artifacts / "model_temperature.pkl").exists():
        import joblib

        models = {
            "Temperature_C": joblib.load(artifacts / "model_temperature.pkl"),
            "Precipitation_mm": joblib.load(artifacts / "model_precipitation.pkl"),
            "Humidity_%": joblib.load(artifacts / "model_humidity.pkl"),
        }
        with open(artifacts / "tabular_feature_cols.json") as f:
            tabular_feature_cols = json.load(f)
        return {"kind": "gbm", "models": models, "tabular_feature_cols": tabular_feature_cols,
                "name": model_dir.name}

    raise FileNotFoundError(
        f"{artifacts} doesn't contain a recognized model (looked for model.keras "
        f"or model_temperature.pkl) — has train.py been run in {model_dir}?"
    )


def _gbm_inference_rows(origin_row: pd.Series, tabular_feature_cols: list[str],
                          horizon: int = TARGET_HORIZON) -> pd.DataFrame:
    """Same feature construction as features_gbm.build_supervised_table, but
    for a single live origin with no known future targets — just the
    horizon x lead-hour feature rows to predict for."""
    h_arr = np.arange(1, horizon + 1)
    table = pd.DataFrame([origin_row[tabular_feature_cols].to_dict()] * horizon)
    table["lead_hour"] = h_arr
    table["lead_hour_sin"] = np.sin(2 * np.pi * h_arr / 24.0)
    table["lead_hour_cos"] = np.cos(2 * np.pi * h_arr / 24.0)

    origin_dt = origin_row["datetime"]
    target_dts = [origin_dt + pd.Timedelta(hours=int(h)) for h in h_arr]
    target_hour = np.array([dt.hour for dt in target_dts])
    target_month = np.array([dt.month for dt in target_dts])
    table["target_hour_sin"] = np.sin(2 * np.pi * target_hour / 24.0)
    table["target_hour_cos"] = np.cos(2 * np.pi * target_hour / 24.0)
    table["target_month_sin"] = np.sin(2 * np.pi * target_month / 12.0)
    table["target_month_cos"] = np.cos(2 * np.pi * target_month / 12.0)
    return table


def predict_next_24h(loaded: dict[str, Any], context_df: pd.DataFrame) -> np.ndarray:
    """context_df: >=168 rows (>= INPUT_WINDOW + a little slack for lag
    features) of raw per-hour observations for ONE district, in the same
    raw-column format data_prep.load_raw_table produces (must include a
    'district' column, even if there's only one). Returns (24, 3) real-unit
    predictions [temperature, precipitation, humidity]."""
    if loaded["kind"] == "deep":
        from config import INPUT_WINDOW

        engineered = data_prep.engineer_features(context_df, extended=False)
        window = engineered.tail(INPUT_WINDOW)[loaded["feature_cols"]].values.astype(np.float32)
        if len(window) < INPUT_WINDOW:
            raise ValueError(f"Only {len(window)} hours of context after feature engineering; "
                              f"need {INPUT_WINDOW}.")

        scaled = loaded["scaler"].transform(window)[np.newaxis, :, :]
        pred_scaled = loaded["model"].predict(scaled, verbose=0)
        real = scaling.inverse_transform_targets(
            pred_scaled, loaded["scaler"], loaded["feature_cols"], TARGET_COLS
        )
        return real[0]

    if loaded["kind"] == "gbm":
        engineered = data_prep.engineer_features(context_df, extended=True)
        tabular_feature_cols = loaded["tabular_feature_cols"]
        available = [c for c in tabular_feature_cols if c in engineered.columns]
        missing = [c for c in tabular_feature_cols if c not in engineered.columns]
        if missing:
            raise ValueError(f"Context data is missing feature(s) this model needs: {missing}")

        origin_row = engineered.iloc[-1]
        rows = _gbm_inference_rows(origin_row, available)

        preds = np.zeros((TARGET_HORIZON, len(TARGET_COLS)), dtype=np.float32)
        for t, target_col in enumerate(TARGET_COLS):
            model = loaded["models"][target_col]
            feature_order = model.feature_name_
            preds[:, t] = model.predict(rows[feature_order])
        return preds

    raise ValueError(f"Unknown model kind: {loaded['kind']}")
