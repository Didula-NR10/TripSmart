"""
predict_future.py
────────────────────
Step 1 of a live 3-way prediction-vs-reality check: fetches context, gets the
GRU model's prediction for the next N hours (default 8), Open-Meteo's own
forecast, and WeatherAPI's own forecast for those same hours — plots the
3-line "prediction only" chart and LOGS everything to disk so
verify_future.py can add a 4th line (what actually happened) once those
hours have passed.

Nobody archives their own past forecasts, so the only honest way to get
"X predicted this, reality was that" is to start now and wait for time to
pass. Run this now, then come back after the horizon elapses and run
verify_future.py.

Usage:
    python predict_future.py Colombo
    python predict_future.py Kandy --hours 6
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
    fetch_weatherapi,
    load_weatherapi_key,
    run_model,
    split_context_and_future,
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
LOG_PATH = OUTPUT_DIR / "prediction_log_3way.jsonl"

COLOR_GRU = "#2a78d6"
COLOR_OM = "#eb6834"
COLOR_WX = "#0a9469"
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
        description="Predict the next N hours with GRU + Open-Meteo + WeatherAPI, log for later verification"
    )
    parser.add_argument("district", type=str, nargs="?", default="Colombo")
    parser.add_argument("--hours", type=int, default=8, help="How many hours ahead to compare (max 24)")
    args = parser.parse_args()

    if args.district not in DISTRICT_COORDS:
        print(f"Unknown district '{args.district}'. Choose one of:")
        print(", ".join(sorted(DISTRICT_COORDS)))
        sys.exit(1)

    horizon = min(args.hours, 24)
    key = load_weatherapi_key()

    print(f"Fetching WeatherAPI data for {args.district} (context + their forecast)...")
    wx_df = fetch_weatherapi(args.district, key)
    context, wx_future = split_context_and_future(wx_df)

    print("Running GRU model on the WeatherAPI-fed context window...")
    real = run_model(context)
    last_obs = context["datetime"].iloc[-1].to_pydatetime()

    wx_fut = wx_future.head(horizon).reset_index(drop=True)
    if len(wx_fut) < horizon:
        raise RuntimeError(f"WeatherAPI only returned {len(wx_fut)}h of forecast; need {horizon}.")

    print(f"Fetching Open-Meteo's own forecast for {args.district}...")
    om_df = fetch_open_meteo(args.district, forecast_days=2)
    _, om_future = split_context_and_future(om_df)
    om_fut = om_future.head(horizon).reset_index(drop=True)
    if len(om_fut) < horizon:
        raise RuntimeError(f"Open-Meteo only returned {len(om_fut)}h of forecast; need {horizon}.")

    rows = []
    for i in range(horizon):
        temp, rain, hum = clamp_physical(
            real[i][0], real[i][1], real[i][2], hour_index=i, district=args.district
        )
        valid = last_obs + pd.Timedelta(hours=i + 1)
        rows.append({
            "valid_time": valid.isoformat(),
            "gru_temp_c": temp, "gru_rain_mm": rain, "gru_hum_pct": hum,
            "om_temp_c": float(om_fut["Temperature_C"].iloc[i]),
            "om_rain_mm": float(om_fut["Precipitation_mm"].iloc[i]),
            "om_hum_pct": float(om_fut["Humidity_%"].iloc[i]),
            "wx_temp_c": float(wx_fut["Temperature_C"].iloc[i]),
            "wx_rain_mm": float(wx_fut["Precipitation_mm"].iloc[i]),
            "wx_hum_pct": float(wx_fut["Humidity_%"].iloc[i]),
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
        (axes[0], "gru_temp_c", "om_temp_c", "wx_temp_c", "Temperature (°C)"),
        (axes[1], "gru_rain_mm", "om_rain_mm", "wx_rain_mm", "Precipitation (mm)"),
        (axes[2], "gru_hum_pct", "om_hum_pct", "wx_hum_pct", "Humidity (%)"),
    ]
    for ax, gru_col, om_col, wx_col, ylabel in panels:
        ax.set_facecolor("#fcfcfb")
        ax.plot(x, merged[gru_col], color=COLOR_GRU, linewidth=2, marker="o", markersize=4,
                 label="GRU (predicted)")
        ax.plot(x, merged[om_col], color=COLOR_OM, linewidth=2, linestyle="--", marker="s", markersize=4,
                 label="Open-Meteo (predicted)")
        ax.plot(x, merged[wx_col], color=COLOR_WX, linewidth=2, linestyle=":", marker="^", markersize=4,
                 label="WeatherAPI (predicted)")
        style_axis(ax, ylabel)

    axes[0].set_title(
        f"Prediction only — {args.district}, next {horizon}h (made at {last_obs:%Y-%m-%d %H:%M})",
        color=COLOR_TEXT, fontsize=12, fontweight="bold", loc="left", pad=14,
    )
    axes[0].legend(loc="upper right", frameon=False, fontsize=9)
    axes[-1].set_xlabel("Valid time (Asia/Colombo)", color=COLOR_TEXT, fontsize=10)
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()

    out_path = OUTPUT_DIR / f"predicted3_{args.district.lower()}_{last_obs:%Y%m%d_%H%M}.png"
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Prediction-only chart saved to {out_path}")

    ready_at = last_obs + pd.Timedelta(hours=horizon)
    print(f"\nNo line has been checked against reality yet.")
    print(f"Come back after {ready_at:%Y-%m-%d %H:%M} and run:")
    print(f"  python verify_future.py {args.district}")


if __name__ == "__main__":
    main()
