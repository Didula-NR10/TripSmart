from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "output"
OUT_DIR.mkdir(exist_ok=True)
OUT_PATH = OUT_DIR / "station_snapshot_2026-08-21_0830.xlsx"

REPORT_TIME = "2026-08-21 0830"
HOUR_END = pd.Timestamp("2026-08-21 08:00")
HOUR_START = pd.Timestamp("2026-08-21 07:00")
WINDOW_START = pd.Timestamp("2026-08-20 09:00")
WINDOW_END = pd.Timestamp("2026-08-21 08:00")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
WEATHERAPI_BASE_URL = "https://api.weatherapi.com/v1"

STATIONS: dict[str, tuple[float, float]] = {
    "JAFFNA":             (9.6615, 80.0255),
    "MULLATIVU":          (9.2671, 80.8128),
    "MANNAR":             (8.9810, 79.9044),
    "VAVUNIYA":           (8.7514, 80.4971),
    "TRINCOMALEE":        (8.5874, 81.2152),
    "ANURADHAPURA":       (8.3114, 80.4037),
    "MAHA ILLUPPALLAMA":  (8.1167, 80.4667),
    "PUTTALAM":           (8.0362, 79.8283),
    "BATTICALOA":         (7.7170, 81.7000),
    "KURUNEGALA":         (7.4867, 80.3647),
    "KATUGASTOTA":        (7.3167, 80.6167),
    "KATUNAYAKE":         (7.1808, 79.8841),
    "COLOMBO":            (6.9271, 79.8612),
    "RATMALANA":          (6.8219, 79.8865),
    "NUWARA ELIYA":       (6.9497, 80.7891),
    "BANDARAWELA":        (6.8306, 80.9986),
    "BADULLA":            (6.9934, 81.0550),
    "RATNAPURA":          (6.6828, 80.3992),
    "GALLE":              (6.0535, 80.2210),
    "HAMBANTOTA":         (6.1241, 81.1185),
    "POTTUVIL":           (6.8747, 81.8367),
    "MATTALA":            (6.2846, 81.1237),
    "MONARAGALA":         (6.8728, 81.3507),
    "POLONNARUWA":        (7.9403, 81.0188),
}

MET_DEPT_REPORT: dict[str, tuple] = {
    "JAFFNA":            (0.0, 0.0, 29.2),
    "MULLATIVU":         (0.0, 0.0, 29.5),
    "MANNAR":            (0.0, 0.0, 28.3),
    "VAVUNIYA":          (0.0, 0.0, 29.6),
    "TRINCOMALEE":       (0.0, 0.0, 30.8),
    "ANURADHAPURA":      (0.0, 0.0, 29.0),
    "MAHA ILLUPPALLAMA": (0.0, 0.0, 28.2),
    "PUTTALAM":          (0.0, 0.0, 29.0),
    "BATTICALOA":        (0.0, 0.0, 30.3),
    "KURUNEGALA":        (0.0, 0.2, 27.8),
    "KATUGASTOTA":       (0.0, 0.5, 24.8),
    "KATUNAYAKE":        (0.0, "Trace", 29.5),
    "COLOMBO":           (0.0, 2.5, 29.2),
    "RATMALANA":         (0.0, 1.1, 29.2),
    "NUWARA ELIYA":      ("Trace", 0.8, 15.5),
    "BANDARAWELA":       (0.0, 0.0, 21.6),
    "BADULLA":           (0.0, 2.3, 25.2),
    "RATNAPURA":         ("Trace", 5.2, 27.7),
    "GALLE":             (0.0, 5.3, 28.0),
    "HAMBANTOTA":        (0.0, 0.0, 28.2),
    "POTTUVIL":          (0.0, 0.0, 30.5),
    "MATTALA":           (0.0, 0.0, 28.5),
    "MONARAGALA":        (0.0, 0.0, 28.8),
    "POLONNARUWA":       (0.0, 0.0, 31.7),
}

def fetch_open_meteo_hourly(lat: float, lon: float) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation",
        "past_days": 7,
        "forecast_days": 1,
        "timezone": "Asia/Colombo",
    }
    resp = requests.get(OPEN_METEO_URL, params=params, timeout=15)
    resp.raise_for_status()
    hourly = resp.json()["hourly"]
    return pd.DataFrame({
        "datetime": pd.to_datetime(hourly["time"]),
        "Temperature_C": hourly["temperature_2m"],
        "Precipitation_mm": hourly["precipitation"],
    })

def load_weatherapi_key() -> str:
    key = os.environ.get("WEATHERAPI_KEY", "").strip()
    if key:
        return key
    env_path = BASE_DIR.parent / "Backend" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("WEATHERAPI_KEY="):
                value = line.split("=", 1)[1].strip()
                if value:
                    return value
    raise RuntimeError(
        "No WeatherAPI key found. Set WEATHERAPI_KEY as an environment variable "
        "before running this script."
    )

def fetch_weatherapi_hourly(lat: float, lon: float, key: str) -> pd.DataFrame:
    q = f"{lat},{lon}"
    hours = []
    for d in ("2026-08-20", "2026-08-21"):
        resp = requests.get(
            f"{WEATHERAPI_BASE_URL}/history.json",
            params={"q": q, "dt": d, "key": key},
            timeout=15,
        )
        resp.raise_for_status()
        hours.extend(resp.json()["forecast"]["forecastday"][0]["hour"])
    return pd.DataFrame({
        "datetime": pd.to_datetime([h["time"] for h in hours]),
        "Temperature_C": [h["temp_c"] for h in hours],
        "Precipitation_mm": [h["precip_mm"] for h in hours],
    })

def snapshot_row(station: str, df: pd.DataFrame) -> dict:
    at_report = df[df["datetime"] == HOUR_END]
    last_hour = df[(df["datetime"] > HOUR_START) & (df["datetime"] <= HOUR_END)]
    window = df[(df["datetime"] >= WINDOW_START) & (df["datetime"] <= WINDOW_END)]

    temp = round(float(at_report["Temperature_C"].iloc[0]), 1) if len(at_report) else None
    rain_last_hour = round(float(last_hour["Precipitation_mm"].sum()), 2) if len(last_hour) else None
    tot_rf = round(float(window["Precipitation_mm"].sum()), 2) if len(window) else None

    return {
        "Station_Name": station,
        "Report_Time": REPORT_TIME,
        "Rainfall (mm)": rain_last_hour,
        "Tot RF since 830am": tot_rf,
        "Temperature (C)": temp,
    }

def build_met_dept_sheet() -> pd.DataFrame:
    rows = []
    for station, (rain, tot_rf, temp) in MET_DEPT_REPORT.items():
        rows.append({
            "Station_Name": station,
            "Report_Time": REPORT_TIME,
            "Rainfall (mm)": rain,
            "Tot RF since 830am": tot_rf,
            "Temperature (C)": temp,
        })
    return pd.DataFrame(rows)

def main() -> None:
    print("Report time: 2026-08-21 08:30 SLT (Asia/Colombo, UTC+05:30) = 2026-08-21 03:00 UTC\n")

    met_df = build_met_dept_sheet()

    print("Fetching Open-Meteo (keyless) for all 24 stations...")
    om_rows = []
    for station, (lat, lon) in STATIONS.items():
        try:
            df = fetch_open_meteo_hourly(lat, lon)
            om_rows.append(snapshot_row(station, df))
        except Exception as e:
            print(f"  ! {station}: {e}")
            om_rows.append({"Station_Name": station, "Report_Time": REPORT_TIME,
                             "Rainfall (mm)": None, "Tot RF since 830am": None, "Temperature (C)": None})
    om_df = pd.DataFrame(om_rows)

    print("Fetching WeatherAPI.com for all 24 stations...")
    try:
        key = load_weatherapi_key()
    except RuntimeError as e:
        print(f"  ! {e}")
        key = None

    wa_rows = []
    if key:
        for station, (lat, lon) in STATIONS.items():
            try:
                df = fetch_weatherapi_hourly(lat, lon, key)
                wa_rows.append(snapshot_row(station, df))
            except Exception as e:
                print(f"  ! {station}: {e}")
                wa_rows.append({"Station_Name": station, "Report_Time": REPORT_TIME,
                                 "Rainfall (mm)": None, "Tot RF since 830am": None, "Temperature (C)": None})
    wa_df = pd.DataFrame(wa_rows) if wa_rows else pd.DataFrame(
        columns=["Station_Name", "Report_Time", "Rainfall (mm)", "Tot RF since 830am", "Temperature (C)"]
    )

    print("\n=== MET DEPT (real station report) ===")
    print(met_df.to_string(index=False))
    print("\n=== OPEN-METEO ===")
    print(om_df.to_string(index=False))
    print("\n=== WEATHERAPI ===")
    print(wa_df.to_string(index=False))

    with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
        met_df.to_excel(writer, sheet_name="MetDept_Station", index=False)
        om_df.to_excel(writer, sheet_name="OpenMeteo", index=False)
        wa_df.to_excel(writer, sheet_name="WeatherAPI", index=False)

    print(f"\nSaved: {OUT_PATH}")

if __name__ == "__main__":
    main()
