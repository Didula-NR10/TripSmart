"""
compare_data_sources.py
─────────────────────────
Three-way comparison for the next 24 hours, same district, same clock hours:

  1. The TripSmart GRU model's own prediction — fed by the last 168 hours of
     REAL observations from WeatherAPI.com (the same source the live backend
     now uses, since the Open-Meteo swap).
  2. Open-Meteo's own forecast product for those same hours (not our model —
     their forecasting engine).
  3. WeatherAPI.com's own forecast product for those same hours (again, their
     engine, not ours).

This answers "how does what our model predicts compare to what the two raw
weather services predict for the same moment" — useful for sanity-checking
the model against independent references, and for seeing how much Open-Meteo
and WeatherAPI disagree with each other in the first place.

Saves a PNG chart to extra/output/ and prints a numeric comparison table
(mean absolute difference between every pair of sources) to the terminal.

Requires a WeatherAPI.com key. Reads WEATHERAPI_KEY from the environment, or
falls back to Backend/.env (whichever line starts with WEATHERAPI_KEY=).

Usage:
    python compare_data_sources.py                 # defaults to Colombo
    python compare_data_sources.py Kandy
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless-safe; script still saves PNGs either way
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from model_pipeline import (
    DISTRICT_COORDS,
    TARGET_HORIZON,
    clamp_physical,
    fetch_open_meteo,
    fetch_weatherapi,
    load_weatherapi_key,
    run_model,
    split_context_and_future,
)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

# Okabe-Ito colorblind-safe triad — extends the 2-series palette from
# compare_with_openmeteo.py (blue/orange kept identical) with a third,
# distinguishable green for WeatherAPI.
COLOR_PREDICTED = "#2a78d6"    # GRU model
COLOR_OPEN_METEO = "#eb6834"   # Open-Meteo's own forecast
COLOR_WEATHERAPI = "#0a9469"   # WeatherAPI's own forecast
COLOR_GRID = "#e1e0d9"
COLOR_AXIS = "#c3c2b7"
COLOR_TEXT = "#0b0b0b"
COLOR_TEXT_MUTED = "#898781"


def build_comparison(district: str, key: str) -> pd.DataFrame:
    print(f"Fetching WeatherAPI data for {district} (context + their forecast)...")
    wx_df = fetch_weatherapi(district, key)
    context, wx_future = split_context_and_future(wx_df)

    print("Running GRU model on the WeatherAPI-fed context window...")
    real = run_model(context)
    last_obs = context["datetime"].iloc[-1].to_pydatetime()

    predicted_rows = []
    for i in range(TARGET_HORIZON):
        temp, rain, humidity = clamp_physical(
            real[i][0], real[i][1], real[i][2], hour_index=i, district=district
        )
        valid = last_obs + pd.Timedelta(hours=i + 1)
        predicted_rows.append({
            "valid_time": valid,
            "pred_temp_c": temp,
            "pred_rain_mm": rain,
            "pred_humidity_pct": humidity,
        })
    predicted = pd.DataFrame(predicted_rows)

    wx_forecast = wx_future.head(TARGET_HORIZON)[
        ["datetime", "Temperature_C", "Precipitation_mm", "Humidity_%"]
    ].rename(columns={
        "datetime": "valid_time",
        "Temperature_C": "wx_temp_c",
        "Precipitation_mm": "wx_rain_mm",
        "Humidity_%": "wx_humidity_pct",
    })

    print(f"Fetching Open-Meteo's own forecast for {district}...")
    om_df = fetch_open_meteo(district, forecast_days=2)
    _, om_future = split_context_and_future(om_df)
    om_forecast = om_future.head(TARGET_HORIZON)[
        ["datetime", "Temperature_C", "Precipitation_mm", "Humidity_%"]
    ].rename(columns={
        "datetime": "valid_time",
        "Temperature_C": "om_temp_c",
        "Precipitation_mm": "om_rain_mm",
        "Humidity_%": "om_humidity_pct",
    })

    merged = predicted.merge(om_forecast, on="valid_time", how="left").merge(
        wx_forecast, on="valid_time", how="left"
    )
    if merged[["om_temp_c", "wx_temp_c"]].isnull().all().any():
        raise RuntimeError(
            "Could not align the model's predicted hours with one of the "
            "reference forecasts' timestamps — the sources disagree on the "
            "current hour by more than expected."
        )
    return merged


def style_axis(ax, ylabel: str) -> None:
    ax.set_ylabel(ylabel, color=COLOR_TEXT, fontsize=10)
    ax.tick_params(colors=COLOR_TEXT_MUTED, labelsize=9)
    ax.grid(True, color=COLOR_GRID, linewidth=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(COLOR_AXIS)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))


def plot_comparison(merged: pd.DataFrame, district: str) -> Path:
    """One axis per unit — three stacked panels, never a dual y-axis."""
    fig, axes = plt.subplots(3, 1, figsize=(10, 11), sharex=True)
    fig.patch.set_facecolor("#fcfcfb")

    x = merged["valid_time"]

    panels = [
        (axes[0], "pred_temp_c", "om_temp_c", "wx_temp_c", "Temperature (°C)"),
        (axes[1], "pred_rain_mm", "om_rain_mm", "wx_rain_mm", "Precipitation (mm)"),
        (axes[2], "pred_humidity_pct", "om_humidity_pct", "wx_humidity_pct", "Humidity (%)"),
    ]

    for ax, pred_col, om_col, wx_col, ylabel in panels:
        ax.set_facecolor("#fcfcfb")
        ax.plot(x, merged[pred_col], color=COLOR_PREDICTED, linewidth=2,
                 marker="o", markersize=4, label="GRU model (predicted)")
        ax.plot(x, merged[om_col], color=COLOR_OPEN_METEO, linewidth=2, linestyle="--",
                 marker="s", markersize=4, label="Open-Meteo (their forecast)")
        ax.plot(x, merged[wx_col], color=COLOR_WEATHERAPI, linewidth=2, linestyle=":",
                 marker="^", markersize=4, label="WeatherAPI (their forecast)")
        style_axis(ax, ylabel)

    axes[0].set_title(
        f"TripSmart GRU vs Open-Meteo vs WeatherAPI — {district}, next {len(merged)}h",
        color=COLOR_TEXT, fontsize=13, fontweight="bold", loc="left", pad=14,
    )
    axes[0].legend(loc="upper right", frameon=False, fontsize=9)
    axes[-1].set_xlabel("Valid time (Asia/Colombo)", color=COLOR_TEXT, fontsize=10)
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"compare_sources_{district.lower()}.png"
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out_path


def print_summary(merged: pd.DataFrame, district: str) -> None:
    def mae(col_a: str, col_b: str) -> float:
        pair = merged[[col_a, col_b]].dropna()
        return float(np.mean(np.abs(pair[col_a] - pair[col_b])))

    print(f"\nPairwise mean absolute difference — {district} (over {len(merged)}h):")
    print(f"{'Metric':<15}{'Model-OM':<12}{'Model-WX':<12}{'OM-WX':<12}")
    print("-" * 51)
    print(f"{'Temperature':<15}{mae('pred_temp_c','om_temp_c'):<12.2f}"
          f"{mae('pred_temp_c','wx_temp_c'):<12.2f}{mae('om_temp_c','wx_temp_c'):<12.2f}")
    print(f"{'Precipitation':<15}{mae('pred_rain_mm','om_rain_mm'):<12.2f}"
          f"{mae('pred_rain_mm','wx_rain_mm'):<12.2f}{mae('om_rain_mm','wx_rain_mm'):<12.2f}")
    print(f"{'Humidity':<15}{mae('pred_humidity_pct','om_humidity_pct'):<12.2f}"
          f"{mae('pred_humidity_pct','wx_humidity_pct'):<12.2f}{mae('om_humidity_pct','wx_humidity_pct'):<12.2f}")

    print(f"\n{'Time':<8}{'Model T':<9}{'OM T':<8}{'WX T':<8}"
          f"{'Model Rn':<10}{'OM Rn':<8}{'WX Rn':<8}"
          f"{'Model Hm':<10}{'OM Hm':<8}{'WX Hm':<8}")
    print("-" * 83)
    for _, r in merged.iterrows():
        print(
            f"{r['valid_time'].strftime('%H:%M'):<8}"
            f"{r['pred_temp_c']:<9}{r['om_temp_c']:<8}{r['wx_temp_c']:<8}"
            f"{r['pred_rain_mm']:<10}{r['om_rain_mm']:<8}{r['wx_rain_mm']:<8}"
            f"{r['pred_humidity_pct']:<10}{r['om_humidity_pct']:<8}{r['wx_humidity_pct']:<8}"
        )


def main() -> None:
    district = sys.argv[1] if len(sys.argv) > 1 else "Colombo"
    if district not in DISTRICT_COORDS:
        print(f"Unknown district '{district}'. Choose one of:")
        print(", ".join(sorted(DISTRICT_COORDS)))
        sys.exit(1)

    key = load_weatherapi_key()
    merged = build_comparison(district, key)
    print_summary(merged, district)

    out_path = plot_comparison(merged, district)
    print(f"\nChart saved to: {out_path}")


if __name__ == "__main__":
    main()
