from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from model_pipeline import (
    DISTRICT_COORDS,
    INPUT_WINDOW,
    RAIN_ZERO_FLOOR_MM,
    TARGET_HORIZON,
    clamp_physical,
    fetch_archive,
    run_model,
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
ARCHIVE_LAG_DAYS = 3

COLOR_RAW = "#2a78d6"
COLOR_TRUTH = "#eb6834"
COLOR_CORRECTED = "#1baf7a"
COLOR_GRID = "#e1e0d9"
COLOR_AXIS = "#c3c2b7"
COLOR_TEXT = "#0b0b0b"
COLOR_TEXT_MUTED = "#898781"

def build_comparison(district: str):
    end = datetime.now() - timedelta(days=ARCHIVE_LAG_DAYS)
    start = end - timedelta(days=INPUT_WINDOW / 24 + 3)

    df = fetch_archive(district, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    df = df.reset_index(drop=True)
    n = len(df)

    o = n - 1 - TARGET_HORIZON
    if o < INPUT_WINDOW - 1:
        raise RuntimeError("Not enough archive history fetched — widen the date range.")

    context = df.iloc[o - INPUT_WINDOW + 1: o + 1].reset_index(drop=True)
    future = df.iloc[o + 1: o + 1 + TARGET_HORIZON].reset_index(drop=True)

    real = run_model(context)
    last_obs = context["datetime"].iloc[-1]

    rows = []
    for i in range(TARGET_HORIZON):
        raw_temp, raw_rain, raw_hum = clamp_physical(real[i][0], real[i][1], real[i][2])
        cor_temp, cor_rain, cor_hum = clamp_physical(
            real[i][0], real[i][1], real[i][2], hour_index=i, district=district
        )
        valid = last_obs + pd.Timedelta(hours=i + 1)
        rows.append({
            "valid_time": valid,
            "raw_temp_c": raw_temp, "cor_temp_c": cor_temp, "truth_temp_c": future["Temperature_C"].iloc[i],
            "raw_rain_mm": raw_rain, "cor_rain_mm": cor_rain, "truth_rain_mm": future["Precipitation_mm"].iloc[i],
            "raw_hum_pct": raw_hum, "cor_hum_pct": cor_hum, "truth_hum_pct": future["Humidity_%"].iloc[i],
        })
    return pd.DataFrame(rows), last_obs

def style_axis(ax, ylabel: str) -> None:
    ax.set_ylabel(ylabel, color=COLOR_TEXT, fontsize=10)
    ax.tick_params(colors=COLOR_TEXT_MUTED, labelsize=9)
    ax.grid(True, color=COLOR_GRID, linewidth=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(COLOR_AXIS)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

def plot(merged: pd.DataFrame, district: str) -> Path:
    fig, axes = plt.subplots(3, 1, figsize=(10, 11), sharex=True)
    fig.patch.set_facecolor("#fcfcfb")
    x = merged["valid_time"]

    panels = [
        (axes[0], "raw_temp_c", "cor_temp_c", "truth_temp_c", "Temperature (°C)"),
        (axes[1], "raw_rain_mm", "cor_rain_mm", "truth_rain_mm", "Precipitation (mm)"),
        (axes[2], "raw_hum_pct", "cor_hum_pct", "truth_hum_pct", "Humidity (%)"),
    ]
    for ax, raw_col, cor_col, truth_col, ylabel in panels:
        ax.set_facecolor("#fcfcfb")
        ax.plot(x, merged[raw_col], color=COLOR_RAW, linewidth=1.6, linestyle="--",
                 marker="o", markersize=3, label="GRU raw (no correction)")
        ax.plot(x, merged[cor_col], color=COLOR_CORRECTED, linewidth=2,
                 marker="o", markersize=4, label="GRU corrected (shipped)")
        ax.plot(x, merged[truth_col], color=COLOR_TRUTH, linewidth=2.4,
                 marker="o", markersize=4, label="Real ground truth (Open-Meteo archive)")
        style_axis(ax, ylabel)

    axes[0].set_title(
        f"GRU forecast vs REAL ground truth — {district}, a recent elapsed 24h window",
        color=COLOR_TEXT, fontsize=13, fontweight="bold", loc="left", pad=14,
    )
    axes[0].legend(loc="upper right", frameon=False, fontsize=9)
    axes[-1].set_xlabel("Valid time (Asia/Colombo)", color=COLOR_TEXT, fontsize=10)
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"ground_truth_{district.lower()}.png"
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out_path

def mae(a, b) -> float:
    return float(np.mean(np.abs(np.array(a) - np.array(b))))

def print_summary(merged: pd.DataFrame, district: str, last_obs) -> None:
    print(f"\n{district} — window ending {last_obs} (Colombo time), vs real ground truth:")
    print(f"  Temperature MAE:   raw {mae(merged.raw_temp_c, merged.truth_temp_c):.3f} degC   "
          f"corrected {mae(merged.cor_temp_c, merged.truth_temp_c):.3f} degC")
    print(f"  Precipitation MAE: raw {mae(merged.raw_rain_mm, merged.truth_rain_mm):.3f} mm   "
          f"corrected {mae(merged.cor_rain_mm, merged.truth_rain_mm):.3f} mm")
    print(f"  Humidity MAE:      raw {mae(merged.raw_hum_pct, merged.truth_hum_pct):.3f} %   "
          f"corrected {mae(merged.cor_hum_pct, merged.truth_hum_pct):.3f} %")

def main() -> None:
    district = sys.argv[1] if len(sys.argv) > 1 else "Colombo"
    if district not in DISTRICT_COORDS:
        print(f"Unknown district '{district}'. Choose one of:")
        print(", ".join(sorted(DISTRICT_COORDS)))
        sys.exit(1)

    merged, last_obs = build_comparison(district)
    print_summary(merged, district, last_obs)
    out_path = plot(merged, district)
    print(f"\nChart saved to: {out_path}")

if __name__ == "__main__":
    main()
