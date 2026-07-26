"""
02_bidirectional_lstm/train.py
──────────────────────────────────
Trains the bidirectional stacked LSTM encoder-decoder (see model.py) and
evaluates it the same way as every other model in alternate_models/, so its
R²/MAE/RMSE numbers are directly comparable.

Usage:
    python train.py --data path/to/your_data.xlsx
    python train.py                                   # uses the synthetic smoke-test sample

Runtime: LSTM is somewhat heavier per-step than GRU, and this one is
bidirectional (roughly 2x the recurrent compute of a unidirectional layer),
so expect this to be the slowest of the three deep models here per epoch.
Recommended on Colab's free T4 GPU rather than local CPU for a full run.

Outputs (in ./artifacts/): same set as 01_gru_seq2seq — model.keras,
scaler.pkl, feature_cols.json, metrics.json, training_curve.png,
per_hour_metrics.png, sample_predictions.png.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
COMMON_DIR = THIS_DIR.parent / "common"
sys.path.insert(0, str(COMMON_DIR))
sys.path.insert(0, str(THIS_DIR))

import joblib
import tensorflow as tf

import config
import data_prep
import metrics
import scaling
from model import build_model

ARTIFACTS_DIR = THIS_DIR / "artifacts"
MODEL_NAME = "02_bidirectional_lstm"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train the bidirectional LSTM forecaster")
    p.add_argument("--data", type=str, default=str(config.DATA_DIR / "synthetic_sample.xlsx"))
    p.add_argument("--sheet", type=str, default=None)
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--batch_size", type=int, default=64)
    p.add_argument("--patience", type=int, default=10)
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if not Path(args.data).exists():
        raise SystemExit(
            f"Data file not found: {args.data}\n"
            f"Run `python ../common/make_synthetic_data.py` first for a smoke test, "
            f"or pass --data path/to/your_real_data.xlsx"
        )

    print(f"Loading data from {args.data} ...")
    df = data_prep.load_raw_table(args.data, sheet_name=args.sheet)
    print(f"Date range: {df['datetime'].min()} to {df['datetime'].max()} | "
          f"districts: {sorted(df['district'].unique())}")

    df = data_prep.engineer_features(df, extended=False)
    feature_cols = data_prep.feature_columns(extended=False)
    X, y, dt_list, dist_list = data_prep.make_windows(df, feature_cols)
    splits = data_prep.chronological_split(X, y, dt_list, dist_list)

    scaler = scaling.fit_scaler(splits["train"]["X"])
    X_train = scaling.scale_windows(splits["train"]["X"], scaler)
    X_val = scaling.scale_windows(splits["val"]["X"], scaler)
    X_test = scaling.scale_windows(splits["test"]["X"], scaler)

    y_train = scaling.scale_targets(splits["train"]["y"], scaler, feature_cols, config.TARGET_COLS)
    y_val = scaling.scale_targets(splits["val"]["y"], scaler, feature_cols, config.TARGET_COLS)

    model = build_model(config.INPUT_WINDOW, len(feature_cols), config.TARGET_HORIZON, len(config.TARGET_COLS))
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="mse", metrics=["mae"])
    model.summary()
    print(f"Total trainable params: {sum(int(tf.size(w)) for w in model.trainable_weights):,}")

    callbacks = [
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=args.patience, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=max(3, args.patience // 2), min_lr=1e-5),
    ]

    start = time.time()
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=args.epochs,
        batch_size=args.batch_size,
        callbacks=callbacks,
        verbose=2,
    )
    elapsed = time.time() - start
    n_epochs_run = len(history.history["loss"])
    print(f"\nTraining took {elapsed / 60:.1f} minutes over {n_epochs_run} epochs "
          f"({elapsed / max(n_epochs_run, 1):.1f}s/epoch).")

    y_pred_scaled = model.predict(X_test, verbose=0)
    y_pred = scaling.inverse_transform_targets(y_pred_scaled, scaler, feature_cols, config.TARGET_COLS)
    y_true = splits["test"]["y"]

    report = metrics.regression_report(y_true, y_pred, model_name=MODEL_NAME)
    report["training_seconds"] = elapsed
    report["epochs_run"] = n_epochs_run
    report["n_train_windows"] = len(X_train)
    report["n_params"] = int(model.count_params())
    metrics.print_report(report)

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    model.save(ARTIFACTS_DIR / "model.keras")
    joblib.dump(scaler, ARTIFACTS_DIR / "scaler.pkl")
    metrics.save_report(report, ARTIFACTS_DIR / "metrics.json")
    metrics.plot_training_curves(history.history, ARTIFACTS_DIR / "training_curve.png", MODEL_NAME)
    metrics.plot_per_hour_metrics(report, ARTIFACTS_DIR / "per_hour_metrics.png", MODEL_NAME)
    metrics.plot_predictions_vs_actual(y_true, y_pred, ARTIFACTS_DIR / "sample_predictions.png", MODEL_NAME)

    with open(ARTIFACTS_DIR / "feature_cols.json", "w") as f:
        json.dump(feature_cols, f, indent=2)

    print(f"\nAll artifacts saved to {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
