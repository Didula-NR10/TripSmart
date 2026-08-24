"""
training.baseline_report
────────────────────────────
No training, no candidate, no promotion — just an honest measurement: pull
real data (see training/data_source.py — defaults to the live database, set
TRAINING_DATA_SOURCE=archive for real historical data with no waiting), hold
out the most recent slice chronologically, and report the CURRENTLY DEPLOYED
model's real MAE / RMSE / R² against real outcomes it never trained on.

This is the number to show an evaluator first: it's the honest, out-of-sample
accuracy of what's actually deployed today, measured the same rigorous way
(chronological holdout, real recorded ground truth) as every other backtest
in this repo — not a training-time metric, and not a claim about a model
that doesn't exist yet.

Usage (from Backend/):
    TRAINING_DATA_SOURCE=archive python -m training.baseline_report
"""
from __future__ import annotations

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("trip_smart.training.baseline_report")


def main() -> int:
    import joblib
    import tensorflow as tf

    from core.config import settings
    from training import config as tcfg
    from training.data_source import fetch_all_districts
    from training.dataset import build_windows, chronological_split, scale_features
    from training.evaluate import evaluate_model

    tcfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Pulling real observations...")
    district_frames = fetch_all_districts()
    if not district_frames:
        log.info("No data available from the selected TRAINING_DATA_SOURCE.")
        return 0

    X, y, dt_list, dist_list = build_windows(district_frames)
    split = chronological_split(X, y, dt_list, dist_list)

    log.info("Loading the currently deployed model...")
    model = tf.keras.models.load_model(settings.MODEL_PATH)
    scaler = joblib.load(settings.SCALER_PATH)

    X_holdout_s = scale_features(split["holdout"]["X"], scaler)
    metrics = evaluate_model(model, scaler, X_holdout_s, split["holdout"]["y"])

    report = {
        "n_districts": len(set(dist_list)),
        "n_windows_total": int(len(X)),
        "n_train": len(split["train"]["X"]),
        "n_val": len(split["val"]["X"]),
        "n_holdout": len(split["holdout"]["X"]),
        "holdout_period": (
            f"{split['holdout']['dt'][0]} to {split['holdout']['dt'][-1]}"
            if len(split["holdout"]["dt"]) else None
        ),
        "metrics": metrics,
    }

    report_path = tcfg.OUTPUT_DIR / "baseline_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))
    log.info("Report:\n%s", json.dumps(report, indent=2, default=str))
    log.info("Saved to %s", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
