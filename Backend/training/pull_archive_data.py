"""
training.pull_archive_data
─────────────────────────────
An ALTERNATIVE to pull_data.py that needs no live app traffic and no
database credentials at all: real historical weather (ERA5-based reanalysis)
from Open-Meteo's free, keyless archive API — the same source and same
fields extra/model_pipeline.py's `fetch_archive` already uses for backtesting.

Use this when you need real numbers NOW (e.g. for an evaluation/demo)
instead of waiting for weather_observations to accumulate from real app
usage — pull_data.py's source. Both return the exact same shape
(dict[district] -> DataFrame with observed_at + the 7 raw fields), so
everything downstream (dataset.py, evaluate.py, rain_hurdle.py) works
identically regardless of which one supplied the data.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

from forecast.utils import DISTRICT_COORDS

log = logging.getLogger("trip_smart.training.pull_archive_data")

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_FIELDS = [
    "temperature_2m", "precipitation", "relativehumidity_2m",
    "cloudcover", "windspeed_10m", "windgusts_10m", "direct_radiation",
]
MAX_RADIATION_WM2 = 1000.0
ARCHIVE_LAG_DAYS = 3  # avoid the last couple of days, which may still be preliminary ERA5T

EXTENDED_HOURLY_FIELDS = HOURLY_FIELDS + ["dewpoint_2m", "pressure_msl", "winddirection_10m"]


def _fetch_one_district(district: str, start_date: str, end_date: str, extended: bool = False) -> pd.DataFrame:
    coords = DISTRICT_COORDS[district]
    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "hourly": ",".join(EXTENDED_HOURLY_FIELDS if extended else HOURLY_FIELDS),
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "Asia/Colombo",
        "windspeed_unit": "kmh",
    }
    resp = requests.get(ARCHIVE_URL, params=params, timeout=30)
    resp.raise_for_status()
    hourly = resp.json()["hourly"]

    df = pd.DataFrame({
        "observed_at": pd.to_datetime(hourly["time"]),
        "Temperature_C": hourly["temperature_2m"],
        "Precipitation_mm": hourly["precipitation"],
        "Humidity_%": hourly["relativehumidity_2m"],
        "CloudCover_%": hourly["cloudcover"],
        "WindSpeed_kmh": hourly["windspeed_10m"],
        "WindGusts_kmh": hourly["windgusts_10m"],
        "radiation": hourly["direct_radiation"],
    })
    if extended:
        df["DewPoint_C"] = hourly["dewpoint_2m"]
        df["Pressure_hPa"] = hourly["pressure_msl"]
        df["WindDirection_deg"] = hourly["winddirection_10m"]

    df = df.ffill().bfill()
    df["DaylightScore"] = (df["radiation"] / MAX_RADIATION_WM2).clip(0.0, 1.0)
    df = df.drop(columns=["radiation"])
    return df


def _fetch_all(lookback_days: int, districts: list[str] | None, extended: bool) -> dict[str, pd.DataFrame]:
    end = datetime.now() - timedelta(days=ARCHIVE_LAG_DAYS)
    start = end - timedelta(days=lookback_days)
    start_str, end_str = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    targets = districts or list(DISTRICT_COORDS)
    out: dict[str, pd.DataFrame] = {}
    for i, district in enumerate(targets):
        try:
            df = _fetch_one_district(district, start_str, end_str, extended=extended)
        except Exception:
            log.exception("%s: archive fetch failed, skipped.", district)
            continue
        log.info("%s: %d hours (%s to %s) [%d/%d]", district, len(df), start_str, end_str,
                  i + 1, len(targets))
        out[district] = df
        time.sleep(0.3)  # be polite to the free, keyless endpoint

    return out


def fetch_all_districts(lookback_days: int = 365, districts: list[str] | None = None) -> dict[str, pd.DataFrame]:
    """Real recorded weather for the last `lookback_days` days, per district —
    the base 7-field contract (forecast.utils.FINAL_FEATURE_COLS' raw
    inputs). Default 365 days keeps a single run's fetch time and API load
    reasonable; raise it if you want more history and don't mind a longer
    run (Open-Meteo's archive itself goes back decades, so the ceiling is
    your own patience, not data availability)."""
    return _fetch_all(lookback_days, districts, extended=False)


def fetch_all_districts_extended(lookback_days: int = 365, districts: list[str] | None = None) -> dict[str, pd.DataFrame]:
    """Same as fetch_all_districts, plus DewPoint_C, Pressure_hPa, and
    WindDirection_deg — the raw ingredients extended_features.py needs.
    Use this for the expanded rain model, not the base temp/humidity model
    (which was trained on, and expects, exactly the original 7 fields)."""
    return _fetch_all(lookback_days, districts, extended=True)
