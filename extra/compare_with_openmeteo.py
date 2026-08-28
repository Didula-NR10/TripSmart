from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from model_pipeline import (
    DISTRICT_COORDS,
    TARGET_HORIZON,
    clamp_physical,
    fetch_open_meteo,
    run_model,
    split_context_and_future,
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

COLOR_PREDICTED = "#2a78d6"
COLOR_OPEN_METEO = "#eb6834"
COLOR_GRID = "#e1e0d9"
COLOR_AXIS = "#c3c2b7"
COLOR_TEXT = "#0b0b0b"
COLOR_TEXT_MUTED = "#898781"

def build_comparison(district: str) -> pd.DataFrame:
    df = fetch_open_meteo(district, forecast_days=2)
    context, future = split_context_and_future(df)

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

    om = future.head(TARGET_HORIZON)[
        ["datetime", "Temperature_C", "Precipitation_mm", "Humidity_%"]
    ].rename(columns={
        "datetime": "valid_time",
        "Temperature_C": "om_temp_c",
        "Precipitation_mm": "om_rain_mm",
        "Humidity_%": "om_humidity_pct",
    })

    merged = predicted.merge(om, on="valid_time", how="inner")
    if merged.empty:
        raise RuntimeError(
            "Could not align model predictions with Open-Meteo's forecast timestamps."
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
    fig, axes = plt.subplots(3, 1, figsize=(10, 11), sharex=True)
    fig.patch.set_facecolor("#fcfcfb")

    x = merged["valid_time"]

    panels = [
        (axes[0], "pred_temp_c", "om_temp_c", "Temperature (°C)"),
        (axes[1], "pred_rain_mm", "om_rain_mm", "Precipitation (mm)"),
        (axes[2], "pred_humidity_pct", "om_humidity_pct", "Humidity (%)"),
    ]

    for ax, pred_col, om_col, ylabel in panels:
        ax.set_facecolor("#fcfcfb")
        ax.plot(x, merged[pred_col], color=COLOR_PREDICTED, linewidth=2,
                 marker="o", markersize=4, label="GRU model (predicted)")
        ax.plot(x, merged[om_col], color=COLOR_OPEN_METEO, linewidth=2,
                 marker="o", markersize=4, label="Open-Meteo (reference forecast)")
        style_axis(ax, ylabel)

    axes[0].set_title(
        f"TripSmart GRU forecast vs Open-Meteo — {district}, next {len(merged)}h",
        color=COLOR_TEXT, fontsize=13, fontweight="bold", loc="left", pad=14,
    )
    axes[0].legend(loc="upper right", frameon=False, fontsize=9)
    axes[-1].set_xlabel("Valid time (Asia/Colombo)", color=COLOR_TEXT, fontsize=10)
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"compare_{district.lower()}.png"
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out_path

def print_summary(merged: pd.DataFrame, district: str) -> None:
    def mae(pred_col: str, om_col: str) -> float:
        return float(np.mean(np.abs(merged[pred_col] - merged[om_col])))

    print(f"\nComparison summary — {district} (mean absolute difference over {len(merged)}h):")
    print(f"  Temperature:   {mae('pred_temp_c', 'om_temp_c'):.2f} °C")
    print(f"  Precipitation: {mae('pred_rain_mm', 'om_rain_mm'):.2f} mm")
    print(f"  Humidity:      {mae('pred_humidity_pct', 'om_humidity_pct'):.2f} %")

    print(f"\n{'Time':<8}{'Pred T':<9}{'OM T':<9}{'Pred Rain':<11}{'OM Rain':<10}{'Pred Hum':<10}{'OM Hum':<8}")
    print("-" * 65)
    for _, r in merged.iterrows():
        print(
            f"{r['valid_time'].strftime('%H:%M'):<8}"
            f"{r['pred_temp_c']:<9}{r['om_temp_c']:<9}"
            f"{r['pred_rain_mm']:<11}{r['om_rain_mm']:<10}"
            f"{r['pred_humidity_pct']:<10}{r['om_humidity_pct']:<8}"
        )

def main() -> None:
    district = sys.argv[1] if len(sys.argv) > 1 else "Colombo"
    if district not in DISTRICT_COORDS:
        print(f"Unknown district '{district}'. Choose one of:")
        print(", ".join(sorted(DISTRICT_COORDS)))
        sys.exit(1)

    print(f"Fetching data and running model for {district}...")
    merged = build_comparison(district)
    print_summary(merged, district)

    out_path = plot_comparison(merged, district)
    print(f"\nChart saved to: {out_path}")

if __name__ == "__main__":
    main()
