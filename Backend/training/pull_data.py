from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import text

from core.database import engine
from forecast.utils import DISTRICT_COORDS

log = logging.getLogger("trip_smart.training.pull_data")

_COLUMN_MAP = {
    "temperature_c": "Temperature_C",
    "precipitation_mm": "Precipitation_mm",
    "humidity_pct": "Humidity_%",
    "cloud_cover_pct": "CloudCover_%",
    "wind_speed_kmh": "WindSpeed_kmh",
    "wind_gusts_kmh": "WindGusts_kmh",
    "daylight_score": "DaylightScore",
}

_QUERY = text(
    """
    SELECT o.observed_at, o.temperature_c, o.precipitation_mm, o.humidity_pct,
           o.cloud_cover_pct, o.wind_speed_kmh, o.wind_gusts_kmh, o.daylight_score
    FROM weather_observations o
    JOIN districts d ON d.id = o.district_id
    WHERE d.name = :district
    ORDER BY o.observed_at ASC
    """
)

def fetch_all_districts() -> dict[str, pd.DataFrame]:
    if engine is None:
        raise RuntimeError(
            "SUPABASE_DB_URL is not set — the retrain pipeline needs the same "
            "database credentials the live backend uses. Set it in the "
            "environment (or CI secret) before running."
        )

    out: dict[str, pd.DataFrame] = {}
    with engine.connect() as conn:
        for district in DISTRICT_COORDS:
            rows = conn.execute(_QUERY, {"district": district}).fetchall()
            if not rows:
                log.info("%s: 0 observations, skipped.", district)
                continue

            df = pd.DataFrame(rows, columns=[
                "observed_at", "temperature_c", "precipitation_mm", "humidity_pct",
                "cloud_cover_pct", "wind_speed_kmh", "wind_gusts_kmh", "daylight_score",
            ])
            df = df.rename(columns=_COLUMN_MAP)
            for col in _COLUMN_MAP.values():
                df[col] = df[col].astype(float)

            df["observed_at"] = pd.to_datetime(df["observed_at"], utc=True)
            df = df.drop_duplicates(subset=["observed_at"]).sort_values("observed_at").reset_index(drop=True)

            log.info("%s: %d observations (%s to %s).", district, len(df),
                      df["observed_at"].iloc[0], df["observed_at"].iloc[-1])
            out[district] = df

    return out
