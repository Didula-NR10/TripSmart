from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import requests

EXTRA_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(EXTRA_DIR))
from model_pipeline import DISTRICT_COORDS

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_FIELDS = [
    "temperature_2m", "precipitation", "relativehumidity_2m",
    "cloudcover", "windspeed_10m", "windgusts_10m", "direct_radiation",
    "pressure_msl", "dew_point_2m",
]

def fetch_live_context(district: str, past_days: int = 15) -> pd.DataFrame:
    if district not in DISTRICT_COORDS:
        raise ValueError(f"Unknown district: '{district}'. See DISTRICT_COORDS in ../../model_pipeline.py.")

    coords = DISTRICT_COORDS[district]
    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "hourly": ",".join(HOURLY_FIELDS),
        "past_days": past_days,
        "forecast_days": 1,
        "timezone": "Asia/Colombo",
        "windspeed_unit": "kmh",
    }
    resp = requests.get(OPEN_METEO_URL, params=params, timeout=20)
    resp.raise_for_status()
    hourly = resp.json()["hourly"]

    df = pd.DataFrame({
        "datetime": pd.to_datetime(hourly["time"]),
        "Temperature_C": hourly["temperature_2m"],
        "Precipitation_mm": hourly["precipitation"],
        "Humidity_%": hourly["relativehumidity_2m"],
        "CloudCover_%": hourly["cloudcover"],
        "WindSpeed_kmh": hourly["windspeed_10m"],
        "WindGusts_kmh": hourly["windgusts_10m"],
        "radiation": hourly["direct_radiation"],
        "Pressure_hPa": hourly["pressure_msl"],
        "DewPoint_C": hourly["dew_point_2m"],
    })
    df = df.ffill().bfill()

    now = pd.Timestamp.now(tz="Asia/Colombo").tz_localize(None)
    df = df[df["datetime"] <= now].reset_index(drop=True)
    df["district"] = district
    return df

def fetch_context_and_future(district: str, past_days: int = 20, forecast_days: int = 2):
    if district not in DISTRICT_COORDS:
        raise ValueError(f"Unknown district: '{district}'. See DISTRICT_COORDS in ../../model_pipeline.py.")

    coords = DISTRICT_COORDS[district]
    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "hourly": ",".join(HOURLY_FIELDS),
        "past_days": past_days,
        "forecast_days": forecast_days,
        "timezone": "Asia/Colombo",
        "windspeed_unit": "kmh",
    }
    resp = requests.get(OPEN_METEO_URL, params=params, timeout=20)
    resp.raise_for_status()
    hourly = resp.json()["hourly"]

    df = pd.DataFrame({
        "datetime": pd.to_datetime(hourly["time"]),
        "Temperature_C": hourly["temperature_2m"],
        "Precipitation_mm": hourly["precipitation"],
        "Humidity_%": hourly["relativehumidity_2m"],
        "CloudCover_%": hourly["cloudcover"],
        "WindSpeed_kmh": hourly["windspeed_10m"],
        "WindGusts_kmh": hourly["windgusts_10m"],
        "radiation": hourly["direct_radiation"],
        "Pressure_hPa": hourly["pressure_msl"],
        "DewPoint_C": hourly["dew_point_2m"],
    })
    df = df.ffill().bfill()
    df["district"] = district

    now = pd.Timestamp.now(tz="Asia/Colombo").tz_localize(None)
    context_df = df[df["datetime"] <= now].reset_index(drop=True)
    future_df = df[df["datetime"] > now].reset_index(drop=True)
    return context_df, future_df
