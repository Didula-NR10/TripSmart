from __future__ import annotations

import json
import os
import time

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
from sklearn.metrics import (
    ConfusionMatrixDisplay, accuracy_score, brier_score_loss, confusion_matrix,
    f1_score, precision_score, recall_score, roc_auc_score, roc_curve,
)
from sklearn.preprocessing import MinMaxScaler

from config import (
    BATCH_SIZE, EARLY_STOPPING_PATIENCE, MAX_EPOCHS, OUTPUT_DIR,
    RAIN_POS_WEIGHT_DAMPING,
)
from data_prep import N_FEATURES, build_split_windows, load_all_districts
from model import (
    best_threshold_by_f1, build_model, compile_model, occurrence_class_weights,
    predict_rain,
)

os.makedirs(OUTPUT_DIR, exist_ok=True)

def mae(pred, actual): return float(np.mean(np.abs(pred - actual)))
def rmse(pred, actual): return float(np.sqrt(np.mean((pred - actual) ** 2)))
def mse(pred, actual): return float(np.mean((pred - actual) ** 2))

def r2(pred, actual):
    p, a = np.asarray(pred).ravel(), np.asarray(actual).ravel()
    ss_res = np.sum((a - p) ** 2)
    ss_tot = np.sum((a - np.mean(a)) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

def scale_in_place(X: np.ndarray, scaler: MinMaxScaler) -> np.ndarray:
    X *= scaler.scale_.astype(np.float32)
    X += scaler.min_.astype(np.float32)
    return X

def main():
    t0 = time.time()

    district_frames = load_all_districts()
    split = build_split_windows(district_frames)
    del district_frames
    import gc
    gc.collect()

    scaler = MinMaxScaler(feature_range=(0, 1))
    rng = np.random.default_rng(42)
    sample_n = min(len(split["train"]["X"]), 5000)
    sample_idx = rng.choice(len(split["train"]["X"]), size=sample_n, replace=False)
    scaler.fit(split["train"]["X"][sample_idx].reshape(-1, N_FEATURES))
    del sample_idx

    X_train_s = scale_in_place(split["train"]["X"], scaler)
    del split["train"]["X"]
    X_val_s = scale_in_place(split["val"]["X"], scaler)
    del split["val"]["X"]
    X_test_s = scale_in_place(split["test"]["X"], scaler)
    del split["test"]["X"]
    gc.collect()

    occ_train, amt_train = split["train"]["y_occurred"], split["train"]["y_total"]
    occ_val, amt_val = split["val"]["y_occurred"], split["val"]["y_total"]
    occ_test, amt_test = split["test"]["y_occurred"], split["test"]["y_total"]

    pos_weight, neg_weight = occurrence_class_weights(occ_train, damping=RAIN_POS_WEIGHT_DAMPING)
    print(f"\n24h rain-occurrence class weights: pos={pos_weight:.2f} neg={neg_weight:.2f} (damped) — "
          f"{int(occ_train.sum()):,} of {len(occ_train):,} training windows have measurable "
          f"rain somewhere in the next 24h ({occ_train.mean():.1%}). Whichever class is the "
          f"minority here gets the weight above 1.0 — on the real dataset that's usually "
          f"'no rain', not 'rain', which the previous pos-only weighting silently missed.\n")

    model = build_model(n_features=N_FEATURES)
    compile_model(model, pos_weight=pos_weight, neg_weight=neg_weight)
    model.summary()

    callbacks = [
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=EARLY_STOPPING_PATIENCE, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=max(2, EARLY_STOPPING_PATIENCE // 2)),
    ]

    history = model.fit(
        X_train_s,
        {"rain_occurrence": occ_train, "rain_amount": amt_train},
        sample_weight={"rain_occurrence": np.ones_like(occ_train), "rain_amount": occ_train},
        validation_data=(
            X_val_s,
            {"rain_occurrence": occ_val, "rain_amount": amt_val},
            {"rain_occurrence": np.ones_like(occ_val), "rain_amount": occ_val},
        ),
        epochs=MAX_EPOCHS, batch_size=BATCH_SIZE, callbacks=callbacks, verbose=2,
    ).history

    val_preds = model.predict(X_val_s, verbose=0)
    threshold = best_threshold_by_f1(occ_val, val_preds["rain_occurrence"])
    print(f"\nTuned 24h occurrence threshold: {threshold:.2f}\n")

    test_preds = model.predict(X_test_s, verbose=0)
    occ_prob = test_preds["rain_occurrence"].ravel()
    amt_pred = test_preds["rain_amount"].ravel()
    combined = predict_rain(occ_prob, amt_pred, threshold=threshold)

    occ_pred_binary = (occ_prob >= threshold).astype(int)
    occ_test_int = occ_test.astype(int)

    cm = confusion_matrix(occ_test_int, occ_pred_binary, labels=[0, 1])
    try:
        roc_auc = float(roc_auc_score(occ_test_int, occ_prob))
    except ValueError:
        roc_auc = None
    occurrence_metrics = {
        "accuracy": float(accuracy_score(occ_test_int, occ_pred_binary)),
        "precision": float(precision_score(occ_test_int, occ_pred_binary, zero_division=0)),
        "recall": float(recall_score(occ_test_int, occ_pred_binary, zero_division=0)),
        "f1": float(f1_score(occ_test_int, occ_pred_binary, zero_division=0)),
        "roc_auc": roc_auc,
        "brier_score": float(brier_score_loss(occ_test_int, occ_prob)),
        "confusion_matrix": cm.tolist(),
        "threshold_used": threshold,
    }

    real_rain_mask = occ_test.astype(bool)
    amount_metrics = {
        "mae": mae(amt_pred[real_rain_mask], amt_test[real_rain_mask]),
        "rmse": rmse(amt_pred[real_rain_mask], amt_test[real_rain_mask]),
        "mse": mse(amt_pred[real_rain_mask], amt_test[real_rain_mask]),
        "r2": r2(amt_pred[real_rain_mask], amt_test[real_rain_mask]),
        "n_real_rain_windows_in_test": int(real_rain_mask.sum()),
    }

    combined_metrics = {
        "mae": mae(combined, amt_test), "rmse": rmse(combined, amt_test),
        "mse": mse(combined, amt_test), "r2": r2(combined, amt_test),
    }

    test_dist = np.array(split["test"]["district"])
    per_district = {}
    for d in sorted(set(test_dist)):
        idx = test_dist == d
        if idx.sum() < 20:
            continue
        per_district[d] = {
            "n_windows": int(idx.sum()),
            "combined_mae": mae(combined[idx], amt_test[idx]),
            "combined_r2": r2(combined[idx], amt_test[idx]),
            "occurrence_f1": float(f1_score(occ_test_int[idx], occ_pred_binary[idx], zero_division=0)),
        }

    model.save(os.path.join(OUTPUT_DIR, "rain24h_model.keras"))
    joblib.dump(scaler, os.path.join(OUTPUT_DIR, "rain24h_scaler.pkl"))

    report = {
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "training_time_seconds": round(time.time() - t0, 1),
        "n_features": N_FEATURES,
        "n_train": len(X_train_s), "n_val": len(X_val_s), "n_test": len(X_test_s),
        "pos_weight_used": pos_weight,
        "neg_weight_used": neg_weight,
        "occurrence": occurrence_metrics,
        "amount": amount_metrics,
        "combined": combined_metrics,
        "per_district": per_district,
    }
    with open(os.path.join(OUTPUT_DIR, "report.json"), "w") as fh:
        json.dump(report, fh, indent=2)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot(history["rain_occurrence_loss"], label="train")
    axes[0].plot(history["val_rain_occurrence_loss"], label="val")
    axes[0].set_title("Occurrence loss"); axes[0].legend()
    axes[1].plot(history["rain_amount_loss"], label="train")
    axes[1].plot(history["val_rain_amount_loss"], label="val")
    axes[1].set_title("Amount loss"); axes[1].legend()
    fig.tight_layout(); fig.savefig(os.path.join(OUTPUT_DIR, "training_curves.png"), dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    ConfusionMatrixDisplay(cm, display_labels=["No rain", "Rain"]).plot(ax=ax, cmap="Blues", colorbar=False)
    ax.set_title("24h rain occurrence — confusion matrix (test set)")
    fig.tight_layout(); fig.savefig(os.path.join(OUTPUT_DIR, "confusion_matrix.png"), dpi=150); plt.close(fig)

    if roc_auc is not None:
        fpr, tpr, _ = roc_curve(occ_test_int, occ_prob)
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.plot(fpr, tpr, label=f"AUC = {roc_auc:.3f}")
        ax.plot([0, 1], [0, 1], "--", color="grey", label="Random guess")
        ax.set_xlabel("False positive rate"); ax.set_ylabel("True positive rate")
        ax.set_title("24h rain occurrence — ROC curve"); ax.legend()
        fig.tight_layout(); fig.savefig(os.path.join(OUTPUT_DIR, "roc_curve.png"), dpi=150); plt.close(fig)

    bins = np.linspace(0, 1, 11)
    bin_idx = np.digitize(occ_prob, bins) - 1
    bin_pred_mean, bin_actual_mean = [], []
    for b in range(10):
        m = bin_idx == b
        if m.sum() > 0:
            bin_pred_mean.append(occ_prob[m].mean())
            bin_actual_mean.append(occ_test[m].mean())
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot(bin_pred_mean, bin_actual_mean, "o-", label="Model")
    ax.plot([0, 1], [0, 1], "--", color="grey", label="Perfectly calibrated")
    ax.set_xlabel("Predicted probability of rain (next 24h)"); ax.set_ylabel("Actual observed frequency")
    ax.set_title("Calibration curve"); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(OUTPUT_DIR, "calibration_curve.png"), dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.scatter(amt_test[real_rain_mask], amt_pred[real_rain_mask], s=4, alpha=0.3)
    lim = max(amt_test[real_rain_mask].max(), amt_pred[real_rain_mask].max(), 1.0)
    ax.plot([0, lim], [0, lim], "--", color="red", label="Perfect prediction")
    ax.set_xlabel("Actual 24h rain total (mm)"); ax.set_ylabel("Predicted 24h rain total (mm)")
    ax.set_title(f"Amount: predicted vs actual (R2={amount_metrics['r2']:.3f})")
    ax.legend(); fig.tight_layout(); fig.savefig(os.path.join(OUTPUT_DIR, "amount_scatter.png"), dpi=150); plt.close(fig)

    rows = [
        ("Occurrence", "Accuracy", f"{occurrence_metrics['accuracy']:.3f}"),
        ("Occurrence", "Precision", f"{occurrence_metrics['precision']:.3f}"),
        ("Occurrence", "Recall", f"{occurrence_metrics['recall']:.3f}"),
        ("Occurrence", "F1", f"{occurrence_metrics['f1']:.3f}"),
        ("Occurrence", "ROC-AUC", f"{roc_auc:.3f}" if roc_auc is not None else "n/a"),
        ("Occurrence", "Brier score", f"{occurrence_metrics['brier_score']:.3f}"),
        ("Amount (rain windows only)", "MAE (mm)", f"{amount_metrics['mae']:.3f}"),
        ("Amount (rain windows only)", "RMSE (mm)", f"{amount_metrics['rmse']:.3f}"),
        ("Amount (rain windows only)", "MSE (mm2)", f"{amount_metrics['mse']:.3f}"),
        ("Amount (rain windows only)", "R2", f"{amount_metrics['r2']:.3f}"),
        ("Combined (final estimate)", "MAE (mm)", f"{combined_metrics['mae']:.3f}"),
        ("Combined (final estimate)", "RMSE (mm)", f"{combined_metrics['rmse']:.3f}"),
        ("Combined (final estimate)", "MSE (mm2)", f"{combined_metrics['mse']:.3f}"),
        ("Combined (final estimate)", "R2", f"{combined_metrics['r2']:.3f}"),
    ]

    col_widths = [28, 14, 10]
    header = ["Category", "Metric", "Value"]
    lines = [
        "TripSmart 24-Hour Rainfall Model — Final Statistics",
        f"Trained: {report['trained_at']}   Time: {report['training_time_seconds']}s",
        f"Train/Val/Test windows: {report['n_train']:,} / {report['n_val']:,} / {report['n_test']:,}",
        "=" * 60,
        "  ".join(c.ljust(w) for c, w in zip(header, col_widths)),
        "-" * 60,
    ]
    for r in rows:
        lines.append("  ".join(str(c).ljust(w) for c, w in zip(r, col_widths)))
    lines.append("=" * 60)
    lines.append(f"Per-district breakdown ({len(per_district)} districts) in report.json")

    table_text = "\n".join(lines)
    print("\n" + table_text)
    with open(os.path.join(OUTPUT_DIR, "final_statistics.txt"), "w", encoding="utf-8") as fh:
        fh.write(table_text)

    fig, ax = plt.subplots(figsize=(7.5, 0.5 + 0.32 * (len(rows) + 1)))
    ax.axis("off")
    fig.suptitle("TripSmart 24-Hour Rainfall Model — Final Statistics", fontsize=12, fontweight="bold", y=0.99)
    tbl = ax.table(cellText=rows, colLabels=header, cellLoc="left", colLoc="left", loc="upper center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.5)
    for (r_i, c_i), cell in tbl.get_celld().items():
        if r_i == 0:
            cell.set_text_props(fontweight="bold", color="white")
            cell.set_facecolor("#1D6E82")
        cell.set_edgecolor("#CBD5D3")
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "final_statistics.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)

    print(f"\nAll outputs saved to ./{OUTPUT_DIR}/")

if __name__ == "__main__":
    main()
