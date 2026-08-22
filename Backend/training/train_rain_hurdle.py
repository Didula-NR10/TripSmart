"""
training.train_rain_hurdle
─────────────────────────────
Standalone script: trains the rain hurdle heads (see rain_hurdle.py) on real
accumulated data and reports whether they beat the existing raw GRU rain
channel on the same held-out split.

Deliberately NOT wired into training/pipeline.py's monthly automation, and
NEVER touches Backend/models/best_checkpoint.keras: this is a new,
un-proven piece of the system. Run it by hand, read the report, and only
once it's been reviewed does wiring it into production become a separate,
deliberate decision — not something that promotes itself the way the
temp/humidity fine-tune loop does.

Honest limitation, stated up front rather than glossed over: this evaluates
the hurdle model against the GRU's OWN raw rain regression (the fair,
apples-to-apples comparison this pipeline can actually run offline). It does
NOT benchmark against the live production rain path (a historical-analog +
WeatherAPI-forecast blend, see forecast/services.py), because that path
needs WeatherAPI's forecast as it existed at prediction time, which isn't
retained anywhere — only real recorded outcomes are. Beating the raw GRU
channel here is necessary evidence the hurdle approach works; beating the
live production blend is a second, separate question that would need
WeatherAPI forecast snapshots collected going forward to answer rigorously.

Usage (from Backend/, with SUPABASE_DB_URL set):
    python -m training.train_rain_hurdle
"""
from __future__ import annotations

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("trip_smart.training.train_rain_hurdle")


def mae(pred, actual) -> float:
    import numpy as np
    return float(np.mean(np.abs(pred - actual)))


def precision_recall_f1(pred_occurred, actual_occurred) -> dict:
    import numpy as np
    tp = float(np.sum((pred_occurred == 1) & (actual_occurred == 1)))
    fp = float(np.sum((pred_occurred == 1) & (actual_occurred == 0)))
    fn = float(np.sum((pred_occurred == 0) & (actual_occurred == 1)))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
            "true_positives": int(tp), "false_positives": int(fp), "false_negatives": int(fn)}


def main() -> int:
    import numpy as np
    import tensorflow as tf
    import joblib

    from core.config import settings
    from training import config as tcfg
    from training.dataset import build_windows, chronological_split, scale_features
    from training.evaluate import evaluate_model, predict_real_units
    from training.pull_data import fetch_all_districts
    from training.rain_hurdle import (
        build_hurdle_model, compile_hurdle_model,
        occurrence_and_amount_targets, predict_rain,
    )

    tcfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Pulling accumulated real observations...")
    district_frames = fetch_all_districts()
    if not district_frames:
        log.info("weather_observations is empty — nothing to train the rain heads on yet.")
        return 0

    X, y, dt_list, dist_list = build_windows(district_frames)
    if len(X) < tcfg.MIN_TOTAL_WINDOWS:
        log.info("Only %d windows (need %d) — not enough data yet for the rain heads either.",
                  len(X), tcfg.MIN_TOTAL_WINDOWS)
        return 0

    split = chronological_split(X, y, dt_list, dist_list)

    base_model = tf.keras.models.load_model(settings.MODEL_PATH)
    scaler = joblib.load(settings.SCALER_PATH)

    X_train_s = scale_features(split["train"]["X"], scaler)
    X_val_s = scale_features(split["val"]["X"], scaler)
    X_holdout_s = scale_features(split["holdout"]["X"], scaler)

    rain_train = split["train"]["y"][:, :, 1]
    rain_val = split["val"]["y"][:, :, 1]
    rain_holdout = split["holdout"]["y"][:, :, 1]

    occ_train, amt_train, w_train = occurrence_and_amount_targets(rain_train)
    occ_val, amt_val, w_val = occurrence_and_amount_targets(rain_val)
    occ_holdout, amt_holdout, _ = occurrence_and_amount_targets(rain_holdout)

    log.info("Building hurdle heads on top of the frozen, already-deployed encoder...")
    hurdle_model = build_hurdle_model(base_model)
    compile_hurdle_model(hurdle_model, learning_rate=tcfg.FINE_TUNE_LR)

    callbacks = [
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=tcfg.EARLY_STOPPING_PATIENCE,
                                          restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5,
                                              patience=max(2, tcfg.EARLY_STOPPING_PATIENCE // 2)),
    ]

    hurdle_model.fit(
        X_train_s,
        {"rain_occurrence": occ_train, "rain_amount": amt_train},
        sample_weight={"rain_occurrence": np.ones_like(occ_train), "rain_amount": w_train},
        validation_data=(
            X_val_s,
            {"rain_occurrence": occ_val, "rain_amount": amt_val},
            {"rain_occurrence": np.ones_like(occ_val), "rain_amount": w_val},
        ),
        epochs=tcfg.FINE_TUNE_MAX_EPOCHS,
        batch_size=tcfg.FINE_TUNE_BATCH_SIZE,
        callbacks=callbacks,
        verbose=2,
    )

    log.info("Evaluating on the held-out slice, against the raw GRU rain channel baseline...")
    baseline = evaluate_model(base_model, scaler, X_holdout_s, split["holdout"]["y"])

    occ_prob, amt_pred = hurdle_model.predict(X_holdout_s, verbose=0)
    hurdle_rain = predict_rain(occ_prob, amt_pred)
    hurdle_mae = mae(hurdle_rain, rain_holdout)

    occ_pred_binary = (occ_prob >= 0.5).astype(int)
    classification_report = precision_recall_f1(occ_pred_binary, occ_holdout.astype(int))

    true_rain_mask = occ_holdout.astype(bool)
    amount_mae_on_real_rain = mae(amt_pred[true_rain_mask], amt_holdout[true_rain_mask]) if true_rain_mask.any() else None

    report = {
        "n_holdout_windows": int(len(X_holdout_s)),
        "baseline_raw_gru_rain_mae": round(baseline["rain_mae_raw"], 3),
        "baseline_floored_gru_rain_mae": round(baseline["rain_mae_floored"], 3),
        "hurdle_combined_rain_mae": round(hurdle_mae, 3),
        "beats_raw_gru": hurdle_mae < baseline["rain_mae_raw"],
        "beats_floored_gru": hurdle_mae < baseline["rain_mae_floored"],
        "occurrence_classification": classification_report,
        "amount_mae_on_hours_it_actually_rained": (
            round(amount_mae_on_real_rain, 3) if amount_mae_on_real_rain is not None else None
        ),
        "note": (
            "Compared against the GRU's own raw rain regression (fair, offline-computable "
            "baseline). NOT compared against the live production analog+WeatherAPI blend — "
            "see this file's module docstring for why that comparison needs forecast-snapshot "
            "data this pipeline doesn't have yet."
        ),
    }

    report_path = tcfg.OUTPUT_DIR / "rain_hurdle_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    log.info("Report: %s", json.dumps(report, indent=2))

    candidate_path = tcfg.OUTPUT_DIR / "rain_hurdle_candidate.keras"
    hurdle_model.save(candidate_path)
    log.info("Candidate hurdle model saved to %s (NOT deployed — review the report first).", candidate_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
