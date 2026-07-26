"""
alternate_models/leaderboard.py
──────────────────────────────────
Reads metrics.json from every model folder that has been trained so far
(01_gru_seq2seq, 02_bidirectional_lstm, 03_seq2seq_attention,
04_lightgbm_multioutput) and prints + charts a side-by-side comparison, so
you can see which one actually won before deciding which to adopt.

Run this any time after training one or more models — it skips any folder
that hasn't been trained yet (no artifacts/metrics.json) rather than
failing.

Usage:
    python leaderboard.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

THIS_DIR = Path(__file__).resolve().parent
COMMON_DIR = THIS_DIR / "common"
sys.path.insert(0, str(COMMON_DIR))
from config import TARGET_COLS  # noqa: E402

MODEL_FOLDERS = [
    "01_gru_seq2seq",
    "02_bidirectional_lstm",
    "03_seq2seq_attention",
    "04_lightgbm_multioutput",
]

OUTPUT_DIR = THIS_DIR / "output"
COLOR_SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]


def load_all_reports() -> dict[str, dict]:
    reports = {}
    for folder in MODEL_FOLDERS:
        metrics_path = THIS_DIR / folder / "artifacts" / "metrics.json"
        if metrics_path.exists():
            with open(metrics_path) as f:
                reports[folder] = json.load(f)
        else:
            print(f"[leaderboard] {folder}: not trained yet (no {metrics_path.relative_to(THIS_DIR)}) — skipped.")
    return reports


def print_table(reports: dict[str, dict]) -> None:
    if not reports:
        print("\nNo trained models found yet. Run at least one folder's train.py first.")
        return

    print(f"\n{'=' * 96}")
    print("LEADERBOARD — overall test-set metrics (higher R2 / lower MAE & RMSE is better)")
    print(f"{'=' * 96}")

    header = f"{'Model':<26}"
    for t in TARGET_COLS:
        header += f"{t + ' R2':<18}{t + ' MAE':<16}"
    print(header)
    print("-" * len(header))

    for folder, report in reports.items():
        row = f"{folder:<26}"
        for t in TARGET_COLS:
            m = report["overall"].get(t, {"r2": float("nan"), "mae": float("nan")})
            row += f"{m['r2']:<18.4f}{m['mae']:<16.4f}"
        print(row)

    print(f"\n{'Model':<26}{'Train time (s)':<18}{'Params / rows':<20}")
    print("-" * 64)
    for folder, report in reports.items():
        t = report.get("training_seconds", float("nan"))
        size = report.get("n_params", report.get("n_train_rows", "?"))
        print(f"{folder:<26}{t:<18.1f}{str(size):<20}")


def plot_leaderboard(reports: dict[str, dict]) -> None:
    if not reports:
        return

    fig, axes = plt.subplots(1, len(TARGET_COLS), figsize=(6 * len(TARGET_COLS), 5))
    if len(TARGET_COLS) == 1:
        axes = [axes]
    fig.patch.set_facecolor("#fcfcfb")

    names = list(reports.keys())
    for ax, target in zip(axes, TARGET_COLS):
        ax.set_facecolor("#fcfcfb")
        r2_values = [reports[n]["overall"].get(target, {}).get("r2", np.nan) for n in names]
        colors = [COLOR_SERIES[i % len(COLOR_SERIES)] for i in range(len(names))]
        ax.bar(range(len(names)), r2_values, color=colors)
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels([n.replace("_", "\n") for n in names], fontsize=8)
        ax.set_title(f"{target} — R2 (test set)", fontsize=11, fontweight="bold")
        ax.axhline(0, color="#898781", linewidth=0.8)
        ax.grid(True, axis="y", color="#e1e0d9", linewidth=0.8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)

    fig.tight_layout()
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / "leaderboard.png"
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"\nLeaderboard chart saved to {out_path}")


def main() -> None:
    reports = load_all_reports()
    print_table(reports)
    plot_leaderboard(reports)


if __name__ == "__main__":
    main()
