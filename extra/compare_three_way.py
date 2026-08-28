from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import requests

from model_pipeline import (
    DISTRICT_COORDS,
    clamp_physical,
    fetch_open_meteo,
    run_model,
    split_context_and_future,
)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
ENV_PATH = BASE_DIR / ".env"
WEATHERAPI_URL = "http://api.weatherapi.com/v1/forecast.json"

def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

COLOR_GRU = "#2a78d6"
COLOR_OM = "#eb6834"
COLOR_WAPI = "#eda100"
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

def fetch_weatherapi(district: str, api_key: str) -> dict:
    coords = DISTRICT_COORDS[district]
    params = {
        "key": api_key,
        "q": f"{coords['lat']},{coords['lon']}",
        "days": 2,
        "aqi": "no",
        "alerts": "no",
    }
    resp = requests.get(WEATHERAPI_URL, params=params, timeout=15)
    if resp.status_code == 401:
        print("WeatherAPI.com rejected the API key (401 Unauthorized).")
        print("Check WEATHERAPI_KEY / --api-key is correct and active.")
        sys.exit(1)
    resp.raise_for_status()
    data = resp.json()

    lookup = {}
    for day in data["forecast"]["forecastday"]:
        for hour in day["hour"]:
            ts = pd.to_datetime(hour["time"])
            lookup[ts] = {
                "temp_c": float(hour["temp_c"]),
                "rain_mm": float(hour["precip_mm"]),
                "hum_pct": float(hour["humidity"]),
            }
    return lookup

def main() -> None:
    parser = argparse.ArgumentParser(
        description="GRU vs Open-Meteo vs WeatherAPI.com — predictions-only comparison"
    )
    parser.add_argument("district", type=str, nargs="?", default="Colombo")
    parser.add_argument("--hours", type=int, default=8, help="How many hours ahead to compare (max 24)")
    parser.add_argument("--api-key", type=str, default=None, help="WeatherAPI.com API key (or set WEATHERAPI_KEY)")
    args = parser.parse_args()

    if args.district not in DISTRICT_COORDS:
        print(f"Unknown district '{args.district}'. Choose one of:")
        print(", ".join(sorted(DISTRICT_COORDS)))
        sys.exit(1)

    load_env_file(ENV_PATH)
    api_key = args.api_key or os.environ.get("WEATHERAPI_KEY")
    if not api_key:
        print("No WeatherAPI.com API key found.")
        print("Get a free one at https://www.weatherapi.com/signup.aspx, then either:")
        print(f"  put WEATHERAPI_KEY=your_key_here in {ENV_PATH}")
        print('  or: $env:WEATHERAPI_KEY = "your_key_here"      (PowerShell)')
        print("or pass it directly: python compare_three_way.py Colombo --api-key YOUR_KEY")
        sys.exit(1)

    horizon = min(args.hours, 24)

    print(f"Fetching Open-Meteo data for {args.district}...")
    df = fetch_open_meteo(args.district, forecast_days=2)
    context, future = split_context_and_future(df)

    print("Running GRU model...")
    real = run_model(context)
    last_obs = context["datetime"].iloc[-1].to_pydatetime()

    om = future.head(horizon).reset_index(drop=True)
    if len(om) < horizon:
        raise RuntimeError(f"Open-Meteo only returned {len(om)}h of forecast; need {horizon}.")

    print(f"Fetching WeatherAPI.com data for {args.district}...")
    wapi_lookup = fetch_weatherapi(args.district, api_key)

    rows = []
    for i in range(horizon):
        temp, rain, hum = clamp_physical(
            real[i][0], real[i][1], real[i][2], hour_index=i, district=args.district
        )
        valid = last_obs + pd.Timedelta(hours=i + 1)

        wapi = wapi_lookup.get(valid)
        if wapi is None:
            print(f"  Warning: WeatherAPI.com has no data for {valid} — skipping that hour.")
            continue

        rows.append({
            "valid_time": valid,
            "gru_temp_c": temp, "gru_rain_mm": rain, "gru_hum_pct": hum,
            "om_temp_c": float(om["Temperature_C"].iloc[i]),
            "om_rain_mm": float(om["Precipitation_mm"].iloc[i]),
            "om_hum_pct": float(om["Humidity_%"].iloc[i]),
            "wapi_temp_c": wapi["temp_c"],
            "wapi_rain_mm": wapi["rain_mm"],
            "wapi_hum_pct": wapi["hum_pct"],
        })

    if not rows:
        print("No overlapping hours between all three sources — nothing to plot.")
        sys.exit(1)

    merged = pd.DataFrame(rows)

    print(f"\n{args.district} — next {len(merged)}h, from {last_obs:%Y-%m-%d %H:%M}")
    print(f"{'Time':<18}{'GRU T':<8}{'OM T':<8}{'WAPI T':<8}"
          f"{'GRU R':<8}{'OM R':<8}{'WAPI R':<8}"
          f"{'GRU H':<8}{'OM H':<8}{'WAPI H':<8}")
    for _, r in merged.iterrows():
        print(f"{r['valid_time']:%Y-%m-%d %H:%M}  "
              f"{r['gru_temp_c']:<6.1f} {r['om_temp_c']:<6.1f} {r['wapi_temp_c']:<6.1f}  "
              f"{r['gru_rain_mm']:<6.2f} {r['om_rain_mm']:<6.2f} {r['wapi_rain_mm']:<6.2f}  "
              f"{r['gru_hum_pct']:<6.1f} {r['om_hum_pct']:<6.1f} {r['wapi_hum_pct']:<6.1f}")

    fig, axes = plt.subplots(3, 1, figsize=(9, 10), sharex=True)
    fig.patch.set_facecolor("#fcfcfb")
    x = merged["valid_time"]
    panels = [
        (axes[0], "gru_temp_c", "om_temp_c", "wapi_temp_c", "Temperature (°C)"),
        (axes[1], "gru_rain_mm", "om_rain_mm", "wapi_rain_mm", "Precipitation (mm)"),
        (axes[2], "gru_hum_pct", "om_hum_pct", "wapi_hum_pct", "Humidity (%)"),
    ]
    for ax, gru_col, om_col, wapi_col, ylabel in panels:
        ax.set_facecolor("#fcfcfb")
        ax.plot(x, merged[gru_col], color=COLOR_GRU, linewidth=2, marker="o", markersize=4,
                 label="GRU (mine)")
        ax.plot(x, merged[om_col], color=COLOR_OM, linewidth=2, marker="o", markersize=4,
                 label="Open-Meteo")
        ax.plot(x, merged[wapi_col], color=COLOR_WAPI, linewidth=2, marker="o", markersize=4,
                 label="WeatherAPI.com")
        style_axis(ax, ylabel)

    axes[0].set_title(
        f"Predictions only — {args.district}, next {len(merged)}h "
        f"(made at {last_obs:%Y-%m-%d %H:%M})",
        color=COLOR_TEXT, fontsize=12, fontweight="bold", loc="left", pad=14,
    )
    axes[0].legend(loc="upper right", frameon=False, fontsize=9)
    axes[-1].set_xlabel("Valid time (Asia/Colombo)", color=COLOR_TEXT, fontsize=10)
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"three_way_{args.district.lower()}_{last_obs:%Y%m%d_%H%M}.png"
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"\nChart saved to {out_path}")
    print("\nNote: none of these three have been checked against reality yet — this")
    print("only shows whether the three forecasters agree, not who's actually right.")

if __name__ == "__main__":
    main()
