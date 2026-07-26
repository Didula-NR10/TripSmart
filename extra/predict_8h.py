"""
predict_8h.py
───────────────
Step 1 of a live prediction-vs-reality check: fetches context, gets the GRU
model's prediction for the next N hours (default 8) AND Open-Meteo's own
forecast for those same hours, plots the two side by side, and LOGS the
predictions to disk so verify_predictions.py can check them against what
actually happens once those hours have passed.

This is the only honest way to get "Open-Meteo predicted X, reality was Y"
— Open-Meteo doesn't archive its own past forecasts, so the comparison has
to start now and wait for time to pass. See extra/README.md for the fuller
explanation of why.

Usage:
    python predict_8h.py Colombo
    python predict_8h.py Kandy --hours 6
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

from model_pipeline import (
    DISTRICT_COORDS,
    clamp_physical,
    fetch_open_meteo,
    run_model,
    split_context_and_future,
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
LOG_PATH = OUTPUT_DIR / "prediction_log.jsonl"

COLOR_GRU = "#2a78d6"
COLOR_OM = "#eb6834"
COLOR_GRID = "#e1e0d9"
COLOR_AXIS = "#c3c2b7"
COLOR_TEXT = "#0b0b0b"
COLOR_TEXT_MUTED = "#898781"


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
    parser = argparse.ArgumentParser(
        description="Predict the next N hours with GRU + Open-Meteo, log for later verification"
    )
    parser.add_argument("district", type=str, nargs="?", default="Colombo")
    parser.add_argument("--hours", type=int, default=8, help="How many hours ahead to compare (max 24)")
    args = parser.parse_args()

    if args.district not in DISTRICT_COORDS:
        print(f"Unknown district '{args.district}'. Choose one of:")
        print(", ".join(sorted(DISTRICT_COORDS)))
        sys.exit(1)

    horizon = min(args.hours, 24)
    print(f"Fetching data for {args.district}...")
    df = fetch_open_meteo(args.district, forecast_days=2)
    context, future = split_context_and_future(df)

    real = run_model(context)
    last_obs = context["datetime"].iloc[-1].to_pydatetime()

    om = future.head(horizon).reset_index(drop=True)
    if len(om) < horizon:
        raise RuntimeError(f"Open-Meteo only returned {len(om)}h of forecast; need {horizon}.")

    rows = []
    for i in range(horizon):
        temp, rain, hum = clamp_physical(
            real[i][0], real[i][1], real[i][2], hour_index=i, district=args.district
        )
        valid = last_obs + pd.Timedelta(hours=i + 1)
        rows.append({
            "valid_time": valid.isoformat(),
            "gru_temp_c": temp, "gru_rain_mm": rain, "gru_hum_pct": hum,
            "om_temp_c": float(om["Temperature_C"].iloc[i]),
            "om_rain_mm": float(om["Precipitation_mm"].iloc[i]),
            "om_hum_pct": float(om["Humidity_%"].iloc[i]),
        })

    record = {
        "district": args.district,
        "origin_time": last_obs.isoformat(),
        "made_at": pd.Timestamp.now().isoformat(),
        "horizon_hours": horizon,
        "hours": rows,
        "verified": False,
    }

    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")
    print(f"Logged prediction to {LOG_PATH}")

    merged = pd.DataFrame(rows)
    merged["valid_time"] = pd.to_datetime(merged["valid_time"])

    fig, axes = plt.subplots(3, 1, figsize=(9, 10), sharex=True)
    fig.patch.set_facecolor("#fcfcfb")
    x = merged["valid_time"]
    panels = [
        (axes[0], "gru_temp_c", "om_temp_c", "Temperature (°C)"),
        (axes[1], "gru_rain_mm", "om_rain_mm", "Precipitation (mm)"),
        (axes[2], "gru_hum_pct", "om_hum_pct", "Humidity (%)"),
    ]
    for ax, gru_col, om_col, ylabel in panels:
        ax.set_facecolor("#fcfcfb")
        ax.plot(x, merged[gru_col], color=COLOR_GRU, linewidth=2, marker="o", markersize=4,
                 label="GRU (predicted)")
        ax.plot(x, merged[om_col], color=COLOR_OM, linewidth=2, marker="o", markersize=4,
                 label="Open-Meteo (predicted)")
        style_axis(ax, ylabel)

    axes[0].set_title(
        f"Prediction only — {args.district}, next {horizon}h (made at {last_obs:%Y-%m-%d %H:%M})",
        color=COLOR_TEXT, fontsize=12, fontweight="bold", loc="left", pad=14,
    )
    axes[0].legend(loc="upper right", frameon=False, fontsize=9)
    axes[-1].set_xlabel("Valid time (Asia/Colombo)", color=COLOR_TEXT, fontsize=10)
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()

    out_path = OUTPUT_DIR / f"predicted_{args.district.lower()}_{last_obs:%Y%m%d_%H%M}.png"
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Prediction-only chart saved to {out_path}")

    ready_at = last_obs + pd.Timedelta(hours=horizon)
    print(f"\nNeither line has been checked against reality yet.")
    print(f"Come back after {ready_at:%Y-%m-%d %H:%M} and run:")
    print(f"  python verify_predictions.py {args.district}")


if __name__ == "__main__":
    main()
