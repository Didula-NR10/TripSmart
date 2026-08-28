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
ARCHIVE_LAG_DAYS = 3

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
        time.sleep(0.3)

    return out

def fetch_all_districts(lookback_days: int = 365, districts: list[str] | None = None) -> dict[str, pd.DataFrame]:
    return _fetch_all(lookback_days, districts, extended=False)

def fetch_all_districts_extended(lookback_days: int = 365, districts: list[str] | None = None) -> dict[str, pd.DataFrame]:
    return _fetch_all(lookback_days, districts, extended=True)
