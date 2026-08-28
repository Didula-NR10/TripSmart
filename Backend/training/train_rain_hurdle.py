from __future__ import annotations

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("trip_smart.training.train_rain_hurdle")

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
    import tensorflow as tf
    import joblib

    from core.config import settings
    from training import config as tcfg
    from training.data_source import fetch_all_districts
    from training.dataset import build_windows, chronological_split, scale_features
    from training.evaluate import evaluate_model, mae as eval_mae, predict_real_units, r2 as eval_r2, rmse as eval_rmse
    from training.rain_hurdle import (
        best_threshold_by_f1, build_hurdle_model, compile_hurdle_model,
        occurrence_and_amount_targets, occurrence_pos_weight, predict_rain,
    )

    tcfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Pulling real observations (see training.data_source for the source)...")
    district_frames = fetch_all_districts()
    if not district_frames:
        log.info("No data available from the selected TRAINING_DATA_SOURCE — nothing to train on yet.")
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

    occ_train, amt_target_train = occurrence_and_amount_targets(rain_train)
    occ_val, amt_target_val = occurrence_and_amount_targets(rain_val)
    occ_holdout, _ = occurrence_and_amount_targets(rain_holdout)

    pos_weight = occurrence_pos_weight(occ_train, damping=tcfg.RAIN_POS_WEIGHT_DAMPING)
    log.info("Rain-hour class weight: %.2f (damping=%.2f applied to the full inverse-frequency "
              "ratio — see rain_hurdle.occurrence_pos_weight's docstring for why full weight "
              "over-corrected in an earlier run) — computed from %d train windows, %d of which "
              "had real rain.", pos_weight, tcfg.RAIN_POS_WEIGHT_DAMPING, occ_train.size, int(occ_train.sum()))

    log.info("Building hurdle heads on top of the frozen, already-deployed encoder...")
    hurdle_model = build_hurdle_model(base_model)
    compile_hurdle_model(hurdle_model, learning_rate=tcfg.FINE_TUNE_LR, pos_weight=pos_weight)

    callbacks = [
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=tcfg.EARLY_STOPPING_PATIENCE,
                                          restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5,
                                              patience=max(2, tcfg.EARLY_STOPPING_PATIENCE // 2)),
    ]

    hurdle_model.fit(
        X_train_s,
        {"rain_occurrence": occ_train, "rain_amount": amt_target_train},
        validation_data=(
            X_val_s,
            {"rain_occurrence": occ_val, "rain_amount": amt_target_val},
        ),
        epochs=tcfg.FINE_TUNE_MAX_EPOCHS,
        batch_size=tcfg.FINE_TUNE_BATCH_SIZE,
        callbacks=callbacks,
        verbose=2,
    )

    log.info("Tuning the occurrence decision threshold on VALIDATION data (never the holdout "
              "we report against, or the reported score stops being honestly out-of-sample)...")
    val_preds = hurdle_model.predict(X_val_s, verbose=0)
    threshold = best_threshold_by_f1(occ_val, val_preds["rain_occurrence"])
    log.info("Tuned threshold: %.2f (a plain 0.5 cutoff is meaningless once the classes are "
              "this imbalanced — the earlier 0.007 recall was measured at an untuned 0.5).", threshold)

    log.info("Evaluating on the held-out slice, against the raw GRU rain channel baseline...")
    baseline = evaluate_model(base_model, scaler, X_holdout_s, split["holdout"]["y"])

    preds = hurdle_model.predict(X_holdout_s, verbose=0)
    occ_prob, amt_pred = preds["rain_occurrence"], preds["rain_amount"]
    hurdle_rain = predict_rain(occ_prob, amt_pred, threshold=threshold)
    hurdle_mae = eval_mae(hurdle_rain, rain_holdout)
    hurdle_rmse = eval_rmse(hurdle_rain, rain_holdout)
    hurdle_r2 = eval_r2(hurdle_rain, rain_holdout)

    occ_pred_binary = (occ_prob >= threshold).astype(int)
    classification_report = precision_recall_f1(occ_pred_binary, occ_holdout.astype(int))

    true_rain_mask = occ_holdout.astype(bool)
    amount_mae_on_real_rain = (
        eval_mae(amt_pred[true_rain_mask], rain_holdout[true_rain_mask]) if true_rain_mask.any() else None
    )

    report = {
        "n_holdout_windows": int(len(X_holdout_s)),
        "occurrence_pos_weight_used": round(pos_weight, 2),
        "occurrence_threshold_used": round(threshold, 2),
        "baseline_raw_gru_rain_mae": round(baseline["rain_mae_raw"], 3),
        "baseline_floored_gru_rain_mae": round(baseline["rain_mae_floored"], 3),
        "baseline_floored_gru_rain_r2": round(baseline["rain_r2_floored"], 3),
        "hurdle_combined_rain_mae": round(hurdle_mae, 3),
        "hurdle_combined_rain_rmse": round(hurdle_rmse, 3),
        "hurdle_combined_rain_r2": round(hurdle_r2, 3),
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
