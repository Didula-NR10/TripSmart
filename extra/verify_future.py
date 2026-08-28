from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from model_pipeline import fetch_weatherapi_actual, load_weatherapi_key

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
LOG_PATH = OUTPUT_DIR / "prediction_log_3way.jsonl"

COLOR_GRU = "#2a78d6"
COLOR_OM = "#eb6834"
COLOR_WX = "#0a9469"
COLOR_TRUTH = "#c0392b"
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

def load_log() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    records = []
    with open(LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records

def save_log(records: list[dict]) -> None:
    with open(LOG_PATH, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

def mae(a, b) -> float:
    return float(np.mean(np.abs(np.array(a) - np.array(b))))

def verify_record(record: dict, key: str) -> bool:
    district = record["district"]
    hours = record["hours"]
    last_valid = pd.to_datetime(hours[-1]["valid_time"])
    now = pd.Timestamp.now(tz="Asia/Colombo").tz_localize(None)
    if last_valid > now:
        return False

    print(f"\nVerifying {district} prediction made at {record['origin_time']} "
          f"({record['horizon_hours']}h horizon)...")

    dates = sorted({pd.to_datetime(h["valid_time"]).date() for h in hours})
    actual_df = fetch_weatherapi_actual(district, dates, key)
    lookup = actual_df.set_index("datetime")

    for h in hours:
        vt = pd.to_datetime(h["valid_time"])
        if vt not in lookup.index:
            print(f"  Warning: no actual data found for {vt} yet — try again shortly.")
            return False
        row = lookup.loc[vt]
        h["actual_temp_c"] = float(row["Temperature_C"])
        h["actual_rain_mm"] = float(row["Precipitation_mm"])
        h["actual_hum_pct"] = float(row["Humidity_%"])

    record["verified"] = True
    return True

def plot_verified(record: dict) -> Path:
    district = record["district"]
    origin = pd.to_datetime(record["origin_time"])
    merged = pd.DataFrame(record["hours"])
    merged["valid_time"] = pd.to_datetime(merged["valid_time"])

    fig, axes = plt.subplots(3, 1, figsize=(9, 10), sharex=True)
    fig.patch.set_facecolor("#fcfcfb")
    x = merged["valid_time"]
    panels = [
        (axes[0], "gru_temp_c", "om_temp_c", "wx_temp_c", "actual_temp_c", "Temperature (°C)"),
        (axes[1], "gru_rain_mm", "om_rain_mm", "wx_rain_mm", "actual_rain_mm", "Precipitation (mm)"),
        (axes[2], "gru_hum_pct", "om_hum_pct", "wx_hum_pct", "actual_hum_pct", "Humidity (%)"),
    ]
    for ax, gru_col, om_col, wx_col, truth_col, ylabel in panels:
        ax.set_facecolor("#fcfcfb")
        ax.plot(x, merged[gru_col], color=COLOR_GRU, linewidth=2, marker="o", markersize=4,
                 label="GRU (predicted)")
        ax.plot(x, merged[om_col], color=COLOR_OM, linewidth=2, linestyle="--", marker="s", markersize=4,
                 label="Open-Meteo (predicted)")
        ax.plot(x, merged[wx_col], color=COLOR_WX, linewidth=2, linestyle=":", marker="^", markersize=4,
                 label="WeatherAPI (predicted)")
        ax.plot(x, merged[truth_col], color=COLOR_TRUTH, linewidth=2.6, marker="D", markersize=4.5,
                 label="Real weather (actual)")
        style_axis(ax, ylabel)

    axes[0].set_title(
        f"Verified — {district}, predicted at {origin:%Y-%m-%d %H:%M} vs what really happened",
        color=COLOR_TEXT, fontsize=12, fontweight="bold", loc="left", pad=14,
    )
    axes[0].legend(loc="upper right", frameon=False, fontsize=9)
    axes[-1].set_xlabel("Valid time (Asia/Colombo)", color=COLOR_TEXT, fontsize=10)
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()

    out_path = OUTPUT_DIR / f"verified3_{district.lower()}_{origin:%Y%m%d_%H%M}.png"
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out_path

def print_summary(record: dict) -> None:
    hours = record["hours"]
    metrics = [
        ("Temperature", "gru_temp_c", "om_temp_c", "wx_temp_c", "actual_temp_c"),
        ("Precipitation", "gru_rain_mm", "om_rain_mm", "wx_rain_mm", "actual_rain_mm"),
        ("Humidity", "gru_hum_pct", "om_hum_pct", "wx_hum_pct", "actual_hum_pct"),
    ]
    print(f"\n{record['district']} — {record['horizon_hours']}h, predicted at {record['origin_time']}")
    print(f"{'Metric':<16}{'GRU MAE':<12}{'Open-Meteo MAE':<16}{'WeatherAPI MAE':<16}{'Closest to reality'}")
    print("-" * 75)
    for name, gru_key, om_key, wx_key, truth_key in metrics:
        g = mae([h[gru_key] for h in hours], [h[truth_key] for h in hours])
        o = mae([h[om_key] for h in hours], [h[truth_key] for h in hours])
        w = mae([h[wx_key] for h in hours], [h[truth_key] for h in hours])
        winner = min([("GRU", g), ("Open-Meteo", o), ("WeatherAPI", w)], key=lambda p: p[1])[0]
        print(f"{name:<16}{g:<12.3f}{o:<16.3f}{w:<16.3f}{winner}")

def main() -> None:
    district_filter = sys.argv[1] if len(sys.argv) > 1 else None
    records = load_log()
    if not records:
        print(f"No predictions logged yet at {LOG_PATH}. Run predict_future.py first.")
        return

    key = load_weatherapi_key()

    any_verified = False
    for record in records:
        if record.get("verified"):
            continue
        if district_filter and record["district"] != district_filter:
            continue
        if verify_record(record, key):
            print_summary(record)
            out_path = plot_verified(record)
            print(f"Verified chart saved to {out_path}")
            any_verified = True
        else:
            last_valid = record["hours"][-1]["valid_time"]
            print(f"{record['district']} prediction (made {record['origin_time']}) hasn't fully "
                  f"elapsed yet — last hour is {last_valid}, check back later.")

    if any_verified:
        save_log(records)
    else:
        print("\nNo predictions were ready to verify yet.")

if __name__ == "__main__":
    main()
