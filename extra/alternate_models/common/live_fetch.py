"""
alternate_models/common/live_fetch.py
────────────────────────────────────────
Fetches a live context window from Open-Meteo, in the same raw-column shape
data_prep.load_raw_table() produces from an xlsx — so a live forecast can be
run through the exact same engineer_features()/feature_columns() pipeline
used at training time.

Separate from ../../model_pipeline.py (the production-mirroring module)
because the LightGBM model's lag-168h feature needs MORE than the
production 168-hour window to compute a real (non-backfilled) value at the
most recent hour — this fetches a configurable number of days instead of
production's fixed 7.

DISTRICT_COORDS is imported from ../../model_pipeline.py (read-only) rather
than redefined here, so the district list never drifts out of sync with the
production one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import requests

EXTRA_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(EXTRA_DIR))
from model_pipeline import DISTRICT_COORDS  # noqa: E402

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_FIELDS = [
    "temperature_2m", "precipitation", "relativehumidity_2m",
    "cloudcover", "windspeed_10m", "windgusts_10m", "direct_radiation",
    # Not part of the base 12-feature contract, but fetched anyway so a
    # LightGBM model trained with the extended feature set (which uses
    # these if present in the training data) doesn't fail at inference
    # time for want of them.
    "pressure_msl", "dew_point_2m",
]


def fetch_live_context(district: str, past_days: int = 15) -> pd.DataFrame:
    """past_days=15 by default (well past the 7 production uses) so
    lag-168h features have real data behind them, not a backfilled guess."""
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
    """Like fetch_live_context, but also returns Open-Meteo's own forecast
    for the hours after 'now' — used by compare_with_openmeteo.py to plot a
    trained model against Open-Meteo's live forecast for the same hours.
    Returns (context_df, future_df), both in the raw-column format."""
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
