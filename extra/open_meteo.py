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
