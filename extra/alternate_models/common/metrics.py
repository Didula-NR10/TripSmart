"""
alternate_models/common/metrics.py
─────────────────────────────────────
Shared evaluation + plotting for every model in alternate_models/, so all
four are scored identically and their numbers are directly comparable.
Reports R², MAE, RMSE — overall, per-target, and per-lead-hour (hour 1
ahead vs hour 24 ahead almost always differ a lot; averaging them away
hides that).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from config import TARGET_COLS

COLOR_SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
COLOR_GRID = "#e1e0d9"
COLOR_AXIS = "#c3c2b7"
COLOR_TEXT = "#0b0b0b"
COLOR_TEXT_MUTED = "#898781"


def regression_report(y_true: np.ndarray, y_pred: np.ndarray, model_name: str) -> dict[str, Any]:
    """y_true, y_pred: (n_samples, horizon, n_targets). Returns a JSON-able
    dict with overall + per-target + per-lead-hour R²/MAE/RMSE."""
    n_samples, horizon, n_targets = y_true.shape
    report: dict[str, Any] = {"model_name": model_name, "n_samples": n_samples, "horizon": horizon}

    overall = {}
    for t, name in enumerate(TARGET_COLS[:n_targets]):
        yt = y_true[:, :, t].ravel()
        yp = y_pred[:, :, t].ravel()
        overall[name] = {
            "r2": float(r2_score(yt, yp)),
            "mae": float(mean_absolute_error(yt, yp)),
            "rmse": float(np.sqrt(mean_squared_error(yt, yp))),
        }
    report["overall"] = overall

    per_hour = {name: [] for name in TARGET_COLS[:n_targets]}
    for t, name in enumerate(TARGET_COLS[:n_targets]):
        for h in range(horizon):
            yt = y_true[:, h, t]
            yp = y_pred[:, h, t]
            per_hour[name].append({
                "hour": h + 1,
                "r2": float(r2_score(yt, yp)) if len(np.unique(yt)) > 1 else float("nan"),
                "mae": float(mean_absolute_error(yt, yp)),
                "rmse": float(np.sqrt(mean_squared_error(yt, yp))),
            })
    report["per_hour"] = per_hour
    return report


def print_report(report: dict[str, Any]) -> None:
    print(f"\n{'=' * 72}")
    print(f"REGRESSION REPORT — {report['model_name']}  ({report['n_samples']} test windows)")
    print(f"{'=' * 72}")
    print(f"\n{'Target':<18}{'R2':<10}{'MAE':<10}{'RMSE':<10}")
    print("-" * 48)
    for name, m in report["overall"].items():
        print(f"{name:<18}{m['r2']:<10.4f}{m['mae']:<10.4f}{m['rmse']:<10.4f}")

    for name, hours in report["per_hour"].items():
        r2_h1, r2_h24 = hours[0]["r2"], hours[-1]["r2"]
        mae_h1, mae_h24 = hours[0]["mae"], hours[-1]["mae"]
        print(f"\n{name}: hour+1 R2={r2_h1:.4f} MAE={mae_h1:.4f}  ->  "
              f"hour+{len(hours)} R2={r2_h24:.4f} MAE={mae_h24:.4f}")


def save_report(report: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"[metrics] Report saved to {out_path}")


def _style_axis(ax, ylabel: str) -> None:
    ax.set_ylabel(ylabel, color=COLOR_TEXT, fontsize=10)
    ax.tick_params(colors=COLOR_TEXT_MUTED, labelsize=9)
    ax.grid(True, color=COLOR_GRID, linewidth=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(COLOR_AXIS)


def plot_training_curves(history: dict, out_path: Path, model_name: str) -> None:
    """`history` is a Keras History.history dict (or an equivalent dict of
    lists) with 'loss' and optionally 'val_loss'. No-op (with a message) for
    models like LightGBM that don't have a Keras-style loss curve."""
    if "loss" not in history:
        print("[metrics] No 'loss' key in history — skipping training curve plot.")
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    epochs = range(1, len(history["loss"]) + 1)
    ax.plot(epochs, history["loss"], color=COLOR_SERIES[0], linewidth=2, label="train loss")
    if "val_loss" in history:
        ax.plot(epochs, history["val_loss"], color=COLOR_SERIES[1], linewidth=2, label="val loss")
    ax.set_title(f"{model_name} — training curve", color=COLOR_TEXT, fontsize=12,
                 fontweight="bold", loc="left")
    ax.set_xlabel("Epoch", color=COLOR_TEXT)
    _style_axis(ax, "Loss")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[metrics] Training curve saved to {out_path}")


def plot_per_hour_metrics(report: dict[str, Any], out_path: Path, model_name: str) -> None:
    """One panel per target: MAE by lead hour (1..24). Shows whether the
    model degrades gracefully with distance or falls apart early."""
    targets = list(report["per_hour"].keys())
    fig, axes = plt.subplots(len(targets), 1, figsize=(9, 3.2 * len(targets)), sharex=True)
    if len(targets) == 1:
        axes = [axes]
    fig.patch.set_facecolor("#fcfcfb")

    for ax, name in zip(axes, targets):
        ax.set_facecolor("#fcfcfb")
        hours = [h["hour"] for h in report["per_hour"][name]]
        mae = [h["mae"] for h in report["per_hour"][name]]
        ax.plot(hours, mae, color=COLOR_SERIES[0], linewidth=2, marker="o", markersize=4)
        _style_axis(ax, f"{name} MAE")

    axes[0].set_title(f"{model_name} — MAE by lead hour (test set)",
                       color=COLOR_TEXT, fontsize=12, fontweight="bold", loc="left")
    axes[-1].set_xlabel("Lead hour", color=COLOR_TEXT)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[metrics] Per-hour metrics plot saved to {out_path}")


def plot_predictions_vs_actual(y_true: np.ndarray, y_pred: np.ndarray, out_path: Path,
                                model_name: str, n_examples: int = 3) -> None:
    """Pick a few random test windows and plot predicted vs actual across
    the 24h horizon, one figure per target — a sanity-check visual, not just
    a scalar metric."""
    n_samples, horizon, n_targets = y_true.shape
    rng = np.random.default_rng(42)
    idxs = rng.choice(n_samples, size=min(n_examples, n_samples), replace=False)

    fig, axes = plt.subplots(n_targets, 1, figsize=(9, 3.2 * n_targets))
    if n_targets == 1:
        axes = [axes]
    fig.patch.set_facecolor("#fcfcfb")

    for t, (ax, name) in enumerate(zip(axes, TARGET_COLS[:n_targets])):
        ax.set_facecolor("#fcfcfb")
        for j, i in enumerate(idxs):
            color = COLOR_SERIES[j % len(COLOR_SERIES)]
            ax.plot(range(1, horizon + 1), y_true[i, :, t], color=color, linewidth=2,
                     label=f"actual #{j+1}" if t == 0 else None)
            ax.plot(range(1, horizon + 1), y_pred[i, :, t], color=color, linewidth=1.4,
                     linestyle="--", label=f"predicted #{j+1}" if t == 0 else None)
        _style_axis(ax, name)

    axes[0].set_title(f"{model_name} — sample predictions vs actual",
                       color=COLOR_TEXT, fontsize=12, fontweight="bold", loc="left")
    axes[0].legend(frameon=False, fontsize=8, ncol=2)
    axes[-1].set_xlabel("Lead hour", color=COLOR_TEXT)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[metrics] Prediction sample plot saved to {out_path}")
