"""
alternate_models/compare_with_openmeteo.py
─────────────────────────────────────────────
Run any trained model from this folder against Open-Meteo's own live
forecast for the same next-24h window and chart the two — the
alternate-models equivalent of ../compare_with_openmeteo.py, pointed at
whichever candidate model you choose instead of the production one.

Same honesty caveat as ../compare_with_openmeteo.py: Open-Meteo's forecast
is a proxy for truth (it hasn't happened yet either), useful for a quick
sanity check. For a real accuracy measurement against what actually
happened, train the model and then adapt the backtesting approach in
../backtest.py (see the top-level README).

Usage:
    python compare_with_openmeteo.py 01_gru_seq2seq
    python compare_with_openmeteo.py 04_lightgbm_multioutput --district Kandy
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
COMMON_DIR = THIS_DIR / "common"
sys.path.insert(0, str(COMMON_DIR))

from inference import load_trained_model, predict_next_24h  # noqa: E402
from live_fetch import fetch_context_and_future  # noqa: E402
from model_pipeline import DISTRICT_COORDS  # noqa: E402

OUTPUT_DIR = THIS_DIR / "output"

COLOR_PREDICTED = "#2a78d6"
COLOR_OPEN_METEO = "#eb6834"
COLOR_GRID = "#e1e0d9"
COLOR_AXIS = "#c3c2b7"
COLOR_TEXT = "#0b0b0b"
COLOR_TEXT_MUTED = "#898781"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare a trained alternate model with Open-Meteo's live forecast")
    p.add_argument("model_dir", type=str, help="e.g. 01_gru_seq2seq")
    p.add_argument("--district", type=str, default="Colombo")
    return p.parse_args()


def style_axis(ax, ylabel: str) -> None:
    ax.set_ylabel(ylabel, color=COLOR_TEXT, fontsize=10)
    ax.tick_params(colors=COLOR_TEXT_MUTED, labelsize=9)
    ax.grid(True, color=COLOR_GRID, linewidth=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(COLOR_AXIS)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))


def main() -> None:
    args = parse_args()
    if args.district not in DISTRICT_COORDS:
        print(f"Unknown district '{args.district}'. Choose one of:")
        print(", ".join(sorted(DISTRICT_COORDS)))
        sys.exit(1)

    model_dir = THIS_DIR / args.model_dir
    print(f"Loading model from {model_dir} ...")
    loaded = load_trained_model(model_dir)
    print(f"Model kind: {loaded['kind']}")

    past_days = 20 if loaded["kind"] == "gbm" else 8
    print(f"Fetching context + Open-Meteo forecast for {args.district}...")
    context_df, future_df = fetch_context_and_future(args.district, past_days=past_days, forecast_days=2)

    real = predict_next_24h(loaded, context_df)
    last_obs = context_df["datetime"].iloc[-1]

    rows = []
    om = future_df.head(24).reset_index(drop=True)
    for i in range(min(24, len(om))):
        valid = last_obs + pd.Timedelta(hours=i + 1)
        rows.append({
            "valid_time": valid,
            "pred_temp_c": real[i][0], "pred_rain_mm": max(0.0, real[i][1]), "pred_hum_pct": real[i][2],
            "om_temp_c": om["Temperature_C"].iloc[i], "om_rain_mm": om["Precipitation_mm"].iloc[i],
            "om_hum_pct": om["Humidity_%"].iloc[i],
        })
    merged = pd.DataFrame(rows)

    def mae(a, b):
        return float(np.mean(np.abs(merged[a] - merged[b])))

    print(f"\n{loaded['name']} vs Open-Meteo — {args.district} (mean absolute difference over {len(merged)}h):")
    print(f"  Temperature:   {mae('pred_temp_c', 'om_temp_c'):.2f} degC")
    print(f"  Precipitation: {mae('pred_rain_mm', 'om_rain_mm'):.2f} mm")
    print(f"  Humidity:      {mae('pred_hum_pct', 'om_hum_pct'):.2f} %")

    fig, axes = plt.subplots(3, 1, figsize=(10, 11), sharex=True)
    fig.patch.set_facecolor("#fcfcfb")
    x = merged["valid_time"]
    panels = [
        (axes[0], "pred_temp_c", "om_temp_c", "Temperature (°C)"),
        (axes[1], "pred_rain_mm", "om_rain_mm", "Precipitation (mm)"),
        (axes[2], "pred_hum_pct", "om_hum_pct", "Humidity (%)"),
    ]
    for ax, pred_col, om_col, ylabel in panels:
        ax.set_facecolor("#fcfcfb")
        ax.plot(x, merged[pred_col], color=COLOR_PREDICTED, linewidth=2, marker="o", markersize=4,
                 label=f"{loaded['name']} (predicted)")
        ax.plot(x, merged[om_col], color=COLOR_OPEN_METEO, linewidth=2, marker="o", markersize=4,
                 label="Open-Meteo (reference forecast)")
        style_axis(ax, ylabel)

    axes[0].set_title(f"{loaded['name']} vs Open-Meteo — {args.district}, next {len(merged)}h",
                       color=COLOR_TEXT, fontsize=13, fontweight="bold", loc="left", pad=14)
    axes[0].legend(loc="upper right", frameon=False, fontsize=9)
    axes[-1].set_xlabel("Valid time (Asia/Colombo)", color=COLOR_TEXT, fontsize=10)
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"compare_{loaded['name']}_{args.district.lower()}.png"
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"\nChart saved to: {out_path}")


if __name__ == "__main__":
    main()
