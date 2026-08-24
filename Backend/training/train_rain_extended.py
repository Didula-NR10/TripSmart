"""
training.train_rain_extended
────────────────────────────────
Item 3 of the improvement plan: trains a FRESH, standalone rain model on the
extended feature set (pressure, dew point, wind direction, rain lags,
rolling rain totals — see extended_features.py) instead of the production
12-feature contract. This is a genuinely new model, not a fine-tune, because
the wider input shape can't reuse the shipped model's encoder.

Fits its own MinMaxScaler on the extended features (the production scaler
was fit on 12 columns and can't be reused for 22). Uses the same
class-weighted occurrence loss + validation-tuned threshold as
train_rain_hurdle.py (see rain_hurdle.py) — this script's entire point is to
isolate "did better FEATURES help", so everything else about the training
recipe is held constant.

NEVER touches Backend/models/ — saves its candidate model, its own scaler,
and its report to training/output/ only.

Usage (from Backend/):
    TRAINING_ARCHIVE_LOOKBACK_DAYS=180 python -m training.train_rain_extended
"""
from __future__ import annotations

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("trip_smart.training.train_rain_extended")


def main() -> int:
    import joblib
    import numpy as np
    import tensorflow as tf
    from sklearn.preprocessing import MinMaxScaler

    from core.config import settings
    from training import config as tcfg
    from training.dataset import build_windows as build_base_windows
    from training.dataset_extended import build_extended_windows, chronological_split
    from training.evaluate import evaluate_model, mae as eval_mae, r2 as eval_r2, rmse as eval_rmse
    from training.extended_features import EXTENDED_FEATURE_COLS
    from training.pull_archive_data import fetch_all_districts_extended
    from training.rain_hurdle import (
        best_threshold_by_f1, build_standalone_rain_model, compile_hurdle_model,
        occurrence_and_amount_targets, occurrence_pos_weight, predict_rain,
    )
    from training.train_rain_hurdle import precision_recall_f1

    tcfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lookback_days = int(os.environ.get("TRAINING_ARCHIVE_LOOKBACK_DAYS", "180"))

    log.info("Pulling EXTENDED real observations (%d days: base fields + pressure/dewpoint/wind "
              "direction)...", lookback_days)
    district_frames = fetch_all_districts_extended(lookback_days=lookback_days)
    if not district_frames:
        log.info("No data available.")
        return 0

    log.info("Building extended (%d-feature) windows...", len(EXTENDED_FEATURE_COLS))
    X_ext, y_ext, dt_ext, dist_ext = build_extended_windows(district_frames)
    split_ext = chronological_split(X_ext, y_ext, dt_ext, dist_ext)

    log.info("Also building the BASE 12-feature windows from the same data, for a fair "
              "same-data baseline comparison against the currently deployed model...")
    from training.dataset import chronological_split as base_chronological_split

    X_base, y_base, dt_base, dist_base = build_base_windows(district_frames)
    split_base = base_chronological_split(X_base, y_base, dt_base, dist_base)

    # Fit a NEW scaler on the extended features — the production scaler.pkl
    # was fit on 12 columns and structurally can't transform 22.
    scaler_ext = MinMaxScaler(feature_range=(0, 1))
    n, w, f = split_ext["train"]["X"].shape
    scaler_ext.fit(split_ext["train"]["X"].reshape(-1, f))

    def scale(X):
        n, w, f = X.shape
        return scaler_ext.transform(X.reshape(-1, f)).reshape(n, w, f).astype(np.float32)

    X_train_s = scale(split_ext["train"]["X"])
    X_val_s = scale(split_ext["val"]["X"])
    X_holdout_s = scale(split_ext["holdout"]["X"])

    rain_train = split_ext["train"]["y"][:, :, 1]
    rain_val = split_ext["val"]["y"][:, :, 1]
    rain_holdout = split_ext["holdout"]["y"][:, :, 1]

    occ_train, amt_target_train = occurrence_and_amount_targets(rain_train)
    occ_val, amt_target_val = occurrence_and_amount_targets(rain_val)
    occ_holdout, _ = occurrence_and_amount_targets(rain_holdout)

    pos_weight = occurrence_pos_weight(occ_train, damping=tcfg.RAIN_POS_WEIGHT_DAMPING)
    log.info("Rain-hour class weight: %.2f (damped, from %d train windows, %d with real rain).",
              pos_weight, occ_train.size, int(occ_train.sum()))

    log.info("Building the standalone extended-feature rain model (%d input features)...", f)
    model = build_standalone_rain_model(input_window=tcfg.INPUT_WINDOW, n_features=f)
    compile_hurdle_model(model, learning_rate=tcfg.FINE_TUNE_LR, pos_weight=pos_weight)

    callbacks = [
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=tcfg.EARLY_STOPPING_PATIENCE,
                                          restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5,
                                              patience=max(2, tcfg.EARLY_STOPPING_PATIENCE // 2)),
    ]

    model.fit(
        X_train_s,
        {"rain_occurrence": occ_train, "rain_amount": amt_target_train},
        validation_data=(X_val_s, {"rain_occurrence": occ_val, "rain_amount": amt_target_val}),
        epochs=tcfg.FINE_TUNE_MAX_EPOCHS,
        batch_size=tcfg.FINE_TUNE_BATCH_SIZE,
        callbacks=callbacks,
        verbose=2,
    )

    log.info("Tuning the occurrence threshold on validation data...")
    val_preds = model.predict(X_val_s, verbose=0)
    threshold = best_threshold_by_f1(occ_val, val_preds["rain_occurrence"])
    log.info("Tuned threshold: %.2f", threshold)

    log.info("Evaluating on held-out data, against the deployed model's own raw rain channel...")
    base_model = tf.keras.models.load_model(settings.MODEL_PATH)
    base_scaler = joblib.load(settings.SCALER_PATH)
    X_base_holdout_s = base_scaler.transform(
        split_base["holdout"]["X"].reshape(-1, split_base["holdout"]["X"].shape[-1])
    ).reshape(split_base["holdout"]["X"].shape).astype("float32")
    baseline = evaluate_model(base_model, base_scaler, X_base_holdout_s, split_base["holdout"]["y"])

    preds = model.predict(X_holdout_s, verbose=0)
    occ_prob, amt_pred = preds["rain_occurrence"], preds["rain_amount"]
    combined = predict_rain(occ_prob, amt_pred, threshold=threshold)

    occ_pred_binary = (occ_prob >= threshold).astype(int)
    classification_report = precision_recall_f1(occ_pred_binary, occ_holdout.astype(int))

    report = {
        "lookback_days": lookback_days,
        "n_features": f,
        "feature_cols": EXTENDED_FEATURE_COLS,
        "n_holdout_windows": int(len(X_holdout_s)),
        "occurrence_pos_weight_used": round(pos_weight, 2),
        "occurrence_threshold_used": round(threshold, 2),
        "baseline_deployed_model_rain_mae": round(baseline["rain_mae_floored"], 3),
        "baseline_deployed_model_rain_r2": round(baseline["rain_r2_floored"], 3),
        "extended_model_rain_mae": round(eval_mae(combined, rain_holdout), 3),
        "extended_model_rain_rmse": round(eval_rmse(combined, rain_holdout), 3),
        "extended_model_rain_r2": round(eval_r2(combined, rain_holdout), 3),
        "occurrence_classification": classification_report,
        "note": (
            "Baseline is the currently deployed 12-feature GRU's own raw rain channel, "
            "evaluated on windows built from the SAME pulled data/period as this model, for "
            "a fair same-data comparison. The extended model uses 22 features (pressure, "
            "dew point, wind direction, rain lags/rolling totals added to the base 12)."
        ),
    }

    report_path = tcfg.OUTPUT_DIR / "rain_extended_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    log.info("Report: %s", json.dumps(report, indent=2))

    model.save(tcfg.OUTPUT_DIR / "rain_extended_candidate.keras")
    joblib.dump(scaler_ext, tcfg.OUTPUT_DIR / "rain_extended_scaler.pkl")
    log.info("Candidate model + its scaler saved to %s (NOT deployed).", tcfg.OUTPUT_DIR)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
