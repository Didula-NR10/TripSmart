"""
04_lightgbm_multioutput/train.py
───────────────────────────────────
Trains gradient-boosted trees (LightGBM) instead of a neural network — see
features_gbm.py for why and how. Three models total (one per target:
temperature, precipitation, humidity), each covering all 24 lead hours via
a `lead_hour` input feature, rather than 72 tiny per-hour models.

Why this folder matters for YOUR hardware specifically: this trains on
CPU only, no GPU required at all, and typically finishes in well under a
minute on a dataset of a few years — genuinely usable on an i5 3rd-gen /
16GB machine without needing Colab. It's also a strong baseline: tree
ensembles with good engineered features are frequently competitive with, or
better than, small deep learning models on tabular-ish weather data, so
treat this as a serious contender, not just "the cheap option."

Usage:
    python train.py --data path/to/your_data.xlsx
    python train.py                                   # uses the synthetic smoke-test sample

Outputs (in ./artifacts/):
    model_temperature.pkl, model_precipitation.pkl, model_humidity.pkl
    tabular_feature_cols.json  - exact feature list each model expects
    metrics.json               - full R²/MAE/RMSE report (same format as the deep models)
    per_hour_metrics.png, sample_predictions.png
    feature_importance.png     - which engineered features each model actually uses
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
import lightgbm as lgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from lightgbm import LGBMRegressor

import config
import data_prep
import metrics
from features_gbm import build_supervised_table, chronological_split_table, model_feature_cols, reshape_to_3d

ARTIFACTS_DIR = THIS_DIR / "artifacts"
MODEL_NAME = "04_lightgbm_multioutput"

TARGET_TO_SLUG = {"Temperature_C": "temperature", "Precipitation_mm": "precipitation", "Humidity_%": "humidity"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train the LightGBM multi-horizon forecaster")
    p.add_argument("--data", type=str, default=str(config.DATA_DIR / "synthetic_sample.xlsx"))
    p.add_argument("--sheet", type=str, default=None)
    p.add_argument("--n_estimators", type=int, default=800)
    p.add_argument("--learning_rate", type=float, default=0.05)
    p.add_argument("--num_leaves", type=int, default=63)
    p.add_argument("--early_stopping_rounds", type=int, default=50)
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

    df = data_prep.engineer_features(df, extended=True)
    tabular_feature_cols = data_prep.feature_columns(extended=True, df=df)
    print(f"Tabular feature columns ({len(tabular_feature_cols)}): {tabular_feature_cols}")

    table = build_supervised_table(df, tabular_feature_cols, config.TARGET_COLS, horizon=config.TARGET_HORIZON)
    splits = chronological_split_table(table)
    train_cols = model_feature_cols(tabular_feature_cols)

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    models = {}
    importances = {}
    start = time.time()

    for target_col in config.TARGET_COLS:
        slug = TARGET_TO_SLUG[target_col]
        y_train = splits["train"][f"target_{target_col}"]
        y_val = splits["val"][f"target_{target_col}"]
        X_train = splits["train"][train_cols]
        X_val = splits["val"][train_cols]

        print(f"\nTraining LightGBM for {target_col} on {len(X_train)} rows "
              f"({splits['train']['origin_datetime'].nunique()} origins)...")
        model = LGBMRegressor(
            n_estimators=args.n_estimators,
            learning_rate=args.learning_rate,
            num_leaves=args.num_leaves,
            objective="regression",
            random_state=42,
            verbose=-1,
        )
        model.fit(
            X_train, y_train,
            eval_X=X_val, eval_y=y_val,
            eval_metric="l1",
            callbacks=[lgb.early_stopping(args.early_stopping_rounds, verbose=False)],
        )
        models[target_col] = model
        importances[target_col] = dict(zip(train_cols, model.feature_importances_.tolist()))
        joblib.dump(model, ARTIFACTS_DIR / f"model_{slug}.pkl")
        print(f"  best_iteration_={model.best_iteration_}")

    elapsed = time.time() - start
    print(f"\nTraining took {elapsed:.1f} seconds for all 3 targets.")

    # Evaluate on test set, reshaped back to (n_origins, 24, 3) for the shared report format
    test_table = splits["test"].copy()
    pred_cols = {}
    for target_col in config.TARGET_COLS:
        pred_col = f"pred_{target_col}"
        test_table[pred_col] = models[target_col].predict(test_table[train_cols])
        pred_cols[target_col] = pred_col

    y_true, y_pred = reshape_to_3d(test_table, pred_cols, config.TARGET_COLS, horizon=config.TARGET_HORIZON)

    report = metrics.regression_report(y_true, y_pred, model_name=MODEL_NAME)
    report["training_seconds"] = elapsed
    report["n_train_rows"] = len(splits["train"])
    report["n_train_origins"] = int(splits["train"]["origin_datetime"].nunique())
    report["best_iterations"] = {t: int(m.best_iteration_) for t, m in models.items()}
    metrics.print_report(report)
    metrics.save_report(report, ARTIFACTS_DIR / "metrics.json")
    metrics.plot_per_hour_metrics(report, ARTIFACTS_DIR / "per_hour_metrics.png", MODEL_NAME)
    metrics.plot_predictions_vs_actual(y_true, y_pred, ARTIFACTS_DIR / "sample_predictions.png", MODEL_NAME)

    with open(ARTIFACTS_DIR / "tabular_feature_cols.json", "w") as f:
        json.dump(tabular_feature_cols, f, indent=2)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    for ax, target_col in zip(axes, config.TARGET_COLS):
        imp = sorted(importances[target_col].items(), key=lambda kv: kv[1], reverse=True)[:10]
        names, values = zip(*imp)
        ax.barh(names[::-1], values[::-1], color="#2a78d6")
        ax.set_title(target_col, fontsize=10)
        ax.tick_params(labelsize=8)
    fig.suptitle(f"{MODEL_NAME} — top 10 feature importances per target", fontweight="bold")
    fig.tight_layout()
    fig.savefig(ARTIFACTS_DIR / "feature_importance.png", dpi=150)
    plt.close(fig)
    print(f"[metrics] Feature importance plot saved to {ARTIFACTS_DIR / 'feature_importance.png'}")

    print(f"\nAll artifacts saved to {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
