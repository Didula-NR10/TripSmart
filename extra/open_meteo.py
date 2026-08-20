"""
open_meteo.py
───────────────
Fetches ACTUAL observed weather (not a forecast) from Open-Meteo's free,
keyless API for all 25 TripSmart districts, for the same 24-hour window as
the Sri Lanka Department of Meteorology's official report in
extra/twentyfour_pdf.pdf:

    24-hour period ending 08:30 SLT on 2026-08-20
    i.e. 2026-08-19 09:00 -> 2026-08-20 08:00 (Asia/Colombo), 24 hourly readings
    (hourly data can't hit the 08:30 boundary exactly; this is the closest
    aligned 24-hour block)

Uses the live forecast endpoint's `past_days` window (model_pipeline's
fetch_open_meteo), NOT the archive/ERA5 endpoint — the ERA5 archive has a
~5-day processing lag, so it does not have data for a date this recent yet.
The past_days window returns real analysed observations for hours before
now, not a prediction.

For each district, records:
    Max_Temp_C   - highest of the 24 hourly readings
    Min_Temp_C   - lowest of the 24 hourly readings
    Rainfall_mm  - sum of the 24 hourly precipitation readings

Writes results to extra/weather_verification.xlsx, sheet "OpenMeteo".
No API key needed.

Usage:
    python open_meteo.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from model_pipeline import DISTRICT_COORDS, fetch_open_meteo

BASE_DIR = Path(__file__).resolve().parent
OUT_PATH = BASE_DIR / "weather_verification.xlsx"

WINDOW_START = pd.Timestamp("2026-08-19 09:00")
WINDOW_END = pd.Timestamp("2026-08-20 08:00")


def fetch_district(district: str) -> dict:
    df = fetch_open_meteo(district, forecast_days=1)
    window = df[(df["datetime"] >= WINDOW_START) & (df["datetime"] <= WINDOW_END)]
    if len(window) != 24:
        print(f"  warning: {district} returned {len(window)}/24 hourly readings")
    return {
        "District": district,
        "Max_Temp_C": round(float(window["Temperature_C"].max()), 1),
        "Min_Temp_C": round(float(window["Temperature_C"].min()), 1),
        "Rainfall_mm": round(float(window["Precipitation_mm"].sum()), 1),
    }


def main() -> None:
    rows = []
    for district in sorted(DISTRICT_COORDS):
        print(f"Fetching Open-Meteo data for {district}...")
        rows.append(fetch_district(district))

    result = pd.DataFrame(rows)
    print("\n" + result.to_string(index=False))

    mode = "a" if OUT_PATH.exists() else "w"
    kwargs = {"if_sheet_exists": "replace"} if mode == "a" else {}
    with pd.ExcelWriter(OUT_PATH, engine="openpyxl", mode=mode, **kwargs) as writer:
        result.to_excel(writer, sheet_name="OpenMeteo", index=False)

    print(f"\nSaved to {OUT_PATH} (sheet: OpenMeteo)")


if __name__ == "__main__":
    main()
