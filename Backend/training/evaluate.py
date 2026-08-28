from __future__ import annotations

import logging

import numpy as np

from forecast.utils import FINAL_FEATURE_COLS, TARGET_INDICES
from training.config import PROMOTION_MARGIN, RAIN_ZERO_FLOOR_MM

log = logging.getLogger("trip_smart.training.evaluate")

def _inverse_transform_batch(y_scaled: np.ndarray, scaler) -> np.ndarray:
    n, h, t = y_scaled.shape
    placeholder = np.zeros((n * h, len(FINAL_FEATURE_COLS)), dtype=np.float32)
    for out_idx, feat_idx in enumerate(TARGET_INDICES):
        placeholder[:, feat_idx] = y_scaled.reshape(n * h, t)[:, out_idx]
    real = scaler.inverse_transform(placeholder)
    return real[:, TARGET_INDICES].reshape(n, h, t)

def predict_real_units(model, X_scaled: np.ndarray, scaler) -> np.ndarray:
    raw = model.predict(X_scaled, verbose=0)
    raw = np.clip(raw, 0.0, 1.0)
    return _inverse_transform_batch(raw, scaler)

def mae(pred: np.ndarray, actual: np.ndarray) -> float:
    return float(np.mean(np.abs(pred - actual)))

def rmse(pred: np.ndarray, actual: np.ndarray) -> float:
    return float(np.sqrt(np.mean((pred - actual) ** 2)))

def r2(pred: np.ndarray, actual: np.ndarray) -> float:
    actual_flat, pred_flat = actual.ravel(), pred.ravel()
    ss_res = np.sum((actual_flat - pred_flat) ** 2)
    ss_tot = np.sum((actual_flat - np.mean(actual_flat)) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

def evaluate_model(model, scaler, X_holdout: np.ndarray, y_holdout: np.ndarray) -> dict:
    pred = predict_real_units(model, X_holdout, scaler)

    temp_pred, rain_pred, hum_pred = pred[:, :, 0], pred[:, :, 1], pred[:, :, 2]
    temp_actual, rain_actual, hum_actual = y_holdout[:, :, 0], y_holdout[:, :, 1], y_holdout[:, :, 2]

    rain_floored = np.where(rain_pred <= RAIN_ZERO_FLOOR_MM, 0.0, rain_pred)

    return {
        "n_holdout": int(len(X_holdout)),
        "temp_mae": mae(temp_pred, temp_actual),
        "temp_rmse": rmse(temp_pred, temp_actual),
        "temp_r2": r2(temp_pred, temp_actual),
        "humidity_mae": mae(hum_pred, hum_actual),
        "humidity_rmse": rmse(hum_pred, hum_actual),
        "humidity_r2": r2(hum_pred, hum_actual),
        "rain_mae_raw": mae(rain_pred, rain_actual),
        "rain_mae_floored": mae(rain_floored, rain_actual),
        "rain_rmse_floored": rmse(rain_floored, rain_actual),
        "rain_r2_floored": r2(rain_floored, rain_actual),
    }

def is_better(candidate: dict, current: dict) -> tuple[bool, str]:
    cand_avg = (candidate["temp_mae"] + candidate["humidity_mae"]) / 2
    curr_avg = (current["temp_mae"] + current["humidity_mae"]) / 2

    if candidate["temp_mae"] > current["temp_mae"] * (1 + PROMOTION_MARGIN):
        return False, f"temperature MAE regressed ({candidate['temp_mae']:.3f} vs {current['temp_mae']:.3f})"
    if candidate["humidity_mae"] > current["humidity_mae"] * (1 + PROMOTION_MARGIN):
        return False, f"humidity MAE regressed ({candidate['humidity_mae']:.3f} vs {current['humidity_mae']:.3f})"

    improvement = (curr_avg - cand_avg) / curr_avg if curr_avg > 0 else 0.0
    if improvement < PROMOTION_MARGIN:
        return False, f"improvement too small to trust ({improvement:.2%} < {PROMOTION_MARGIN:.2%} margin)"

    return True, f"combined temp+humidity MAE improved {improvement:.2%} ({curr_avg:.3f} -> {cand_avg:.3f})"
