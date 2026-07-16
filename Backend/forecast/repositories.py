"""
forecast.repositories
─────────────────────
Everything that talks to the outside world: the upstream weather API, the model
artifacts on disk, and Supabase. Services depend on this; this depends on
nothing above it.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
import numpy as np
import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.config import settings
from core.database import db_available, get_session
from core.models import District, ForecastRun, WeatherObservation
from forecast.utils import DISTRICT_COORDS, MAX_RADIATION_WM2

log = logging.getLogger("trip_smart.forecast.repo")


# ──────────────────────────────────────────────────────────────────────────────
# 1. The model — loaded ONCE, lazily
# ──────────────────────────────────────────────────────────────────────────────

class ModelRepository:
    """Holds the Keras model and the fitted scaler.

    Loading is lazy and cached: TensorFlow costs seconds and hundreds of MB, so
    we refuse to pay that at import time (it would slow every worker boot, even
    ones that never forecast). The first request pays; the rest are free.
    """

    _model = None
    _scaler = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            import tensorflow as tf  # imported here, not at module top, on purpose

            path = settings.MODEL_PATH
            log.info("Loading GRU forecaster from %s ...", path)
            cls._model = tf.keras.models.load_model(path)

            # Warm-up pass: the first predict() otherwise pays graph-compilation
            # cost, which would land on an unlucky user instead of on startup.
            dummy = np.zeros((1, settings.INPUT_WINDOW, 12), dtype=np.float32)
            cls._model.predict(dummy, verbose=0)
            log.info("Model ready. Input shape: %s", cls._model.input_shape)
        return cls._model

    @classmethod
    def get_scaler(cls):
        if cls._scaler is None:
            import joblib

            log.info("Loading scaler from %s ...", settings.SCALER_PATH)
            scaler = joblib.load(settings.SCALER_PATH)

            if scaler.n_features_in_ != 12:
                raise ValueError(
                    f"Scaler was fitted on {scaler.n_features_in_} features, "
                    "but the feature contract defines 12. The artifacts and the "
                    "code are out of sync — refusing to serve wrong numbers."
                )
            cls._scaler = scaler
        return cls._scaler

    @classmethod
    def is_ready(cls) -> bool:
        import os

        return os.path.exists(settings.MODEL_PATH) and os.path.exists(settings.SCALER_PATH)


# ──────────────────────────────────────────────────────────────────────────────
# 2. Upstream observations — Open-Meteo
# ──────────────────────────────────────────────────────────────────────────────

class WeatherRepository:
    """Fetches the 168-hour context window the model needs to see."""

    HOURLY_FIELDS = [
        "temperature_2m",
        "precipitation",
        "relativehumidity_2m",
        "cloudcover",
        "windspeed_10m",
        "windgusts_10m",
        "direct_radiation",
    ]

    async def fetch_context_window(self, district: str) -> pd.DataFrame:
        """The last 168 consecutive hours of RECORDED weather for a district.

        `past_days=7` gives exactly 168 hours of actuals. We ask for one forecast
        day too because Open-Meteo requires a non-zero horizon — those future
        rows are then discarded, since feeding the model a forecast as if it were
        an observation would quietly corrupt the context.
        """
        if district not in DISTRICT_COORDS:
            raise ValueError(f"Unknown district: '{district}'")

        coords = DISTRICT_COORDS[district]
        params = {
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "hourly": ",".join(self.HOURLY_FIELDS),
            "past_days": 7,
            "forecast_days": 1,
            "timezone": "Asia/Colombo",
            "windspeed_unit": "kmh",
        }

        # One retry: when two districts are requested back-to-back (the
        # comparer), the first request's model load can stall the event loop
        # long enough for this call's read to time out spuriously.
        async with httpx.AsyncClient(timeout=settings.OPEN_METEO_TIMEOUT) as client:
            try:
                response = await client.get(settings.OPEN_METEO_URL, params=params)
            except httpx.TimeoutException:
                response = await client.get(settings.OPEN_METEO_URL, params=params)

        if response.status_code != 200:
            raise RuntimeError(
                f"Open-Meteo returned {response.status_code}: {response.text[:200]}"
            )

        hourly = response.json()["hourly"]

        df = pd.DataFrame({
            "datetime": pd.to_datetime(hourly["time"]),
            "Temperature_C": hourly["temperature_2m"],
            "Precipitation_mm": hourly["precipitation"],
            "Humidity_%": hourly["relativehumidity_2m"],
            "CloudCover_%": hourly["cloudcover"],
            "WindSpeed_kmh": hourly["windspeed_10m"],
            "WindGusts_kmh": hourly["windgusts_10m"],
            "radiation": hourly["direct_radiation"],
        })

        # Drop anything at or beyond the current hour: those are predictions.
        # Open-Meteo rows are Colombo wall time, so compare in Colombo wall
        # time explicitly — the server's own clock may be in any timezone.
        now = pd.Timestamp.now(tz="Asia/Colombo").tz_localize(None)
        df = df[df["datetime"] <= now].copy()
        df = df.tail(settings.INPUT_WINDOW).reset_index(drop=True)

        if len(df) < settings.INPUT_WINDOW:
            raise RuntimeError(
                f"Only {len(df)} hours of observations available; "
                f"{settings.INPUT_WINDOW} are required."
            )

        # Upstream gaps would become NaNs and poison the whole window.
        df = df.ffill().bfill()

        df["Hour"] = df["datetime"].dt.hour
        df["Month"] = df["datetime"].dt.month
        df["DaylightScore"] = (df["radiation"] / MAX_RADIATION_WM2).clip(0.0, 1.0)

        return df

    CURRENT_FIELDS = [
        "temperature_2m",
        "relative_humidity_2m",
        "apparent_temperature",
        "precipitation",
        "weather_code",
        "cloud_cover",
        "pressure_msl",
        "wind_speed_10m",
        "wind_gusts_10m",
        "wind_direction_10m",
        "uv_index",
        "is_day",
    ]

    async def fetch_current(self, district: str) -> Dict[str, Any]:
        """A live snapshot for right now — no model involved, straight from
        Open-Meteo's `current` block. Used by the district comparer's
        "current conditions" mode, where the ask is what a traveler would see
        by checking a weather app at this exact moment."""
        if district not in DISTRICT_COORDS:
            raise ValueError(f"Unknown district: '{district}'")

        coords = DISTRICT_COORDS[district]
        params = {
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "current": ",".join(self.CURRENT_FIELDS),
            "timezone": "Asia/Colombo",
            "windspeed_unit": "kmh",
        }

        async with httpx.AsyncClient(timeout=settings.OPEN_METEO_TIMEOUT) as client:
            response = await client.get(settings.OPEN_METEO_URL, params=params)

        if response.status_code != 200:
            raise RuntimeError(
                f"Open-Meteo returned {response.status_code}: {response.text[:200]}"
            )

        return response.json()["current"]


# ──────────────────────────────────────────────────────────────────────────────
# 3. Persistence — Supabase Postgres via SQLAlchemy (optional)
# ──────────────────────────────────────────────────────────────────────────────

class DistrictLookup:
    """Name → UUID map for the seeded districts table, loaded once."""

    _ids: Optional[Dict[str, Any]] = None

    @classmethod
    def id_for(cls, district: str) -> Optional[Any]:
        if not db_available():
            return None
        if cls._ids is None:
            try:
                with get_session() as session:
                    cls._ids = {d.name: d.id for d in session.query(District).all()}
            except Exception as e:
                log.warning("District lookup failed: %s", e)
                return None
        return cls._ids.get(district)


class ObservationRepository:
    """Persists the fetched context windows into weather_observations, one row
    per district-hour. The unique (district_id, observed_at) constraint makes
    every save an idempotent top-up: overlapping windows skip existing hours."""

    def save_window(self, district: str, frame: pd.DataFrame) -> None:
        district_id = DistrictLookup.id_for(district)
        if district_id is None:
            return

        # Open-Meteo timestamps arrive naive in Asia/Colombo; observed_at is
        # timestamptz, so localise before insert or hours would shift by 5:30.
        observed = pd.DatetimeIndex(frame["datetime"]).tz_localize("Asia/Colombo")

        rows = [
            {
                "district_id": district_id,
                "observed_at": observed[i].to_pydatetime(),
                "temperature_c": round(float(r["Temperature_C"]), 2),
                "precipitation_mm": round(float(r["Precipitation_mm"]), 3),
                "humidity_pct": round(float(r["Humidity_%"]), 1),
                "cloud_cover_pct": round(float(r["CloudCover_%"]), 1),
                "wind_speed_kmh": round(float(r["WindSpeed_kmh"]), 2),
                "wind_gusts_kmh": round(float(r["WindGusts_kmh"]), 2),
                "daylight_score": round(float(r["DaylightScore"]), 4),
            }
            for i, (_, r) in enumerate(frame.iterrows())
        ]

        try:
            with get_session() as session:
                stmt = pg_insert(WeatherObservation).values(rows)
                stmt = stmt.on_conflict_do_nothing(constraint="uq_district_hour")
                session.execute(stmt)
        except Exception as e:
            # Observation history is a nice-to-have; the forecast must not fail
            # because a write did.
            log.warning("Could not persist observations for %s: %s", district, e)


class ForecastRepository:
    """Stores completed runs so we can serve repeats without re-running the GRU."""

    def get_fresh(self, district: str) -> Optional[dict]:
        """The most recent run for this district, if it's still within the cache
        window. Upstream data is hourly — re-running the model sooner produces the
        same answer at the cost of a few hundred ms of CPU."""
        district_id = DistrictLookup.id_for(district)
        if district_id is None:
            return None

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.FORECAST_CACHE_MINUTES)
        try:
            with get_session() as session:
                run = (
                    session.query(ForecastRun)
                    .filter(
                        ForecastRun.district_id == district_id,
                        ForecastRun.forecast_origin >= cutoff,
                    )
                    .order_by(ForecastRun.forecast_origin.desc())
                    .first()
                )
                return {"payload": run.payload} if run else None
        except Exception as e:
            log.warning("Cache lookup failed (serving fresh): %s", e)
            return None

    def save(self, district: str, origin: datetime, payload: dict) -> None:
        district_id = DistrictLookup.id_for(district)
        if district_id is None:
            return
        try:
            with get_session() as session:
                session.add(ForecastRun(
                    district_id=district_id,
                    forecast_origin=origin,
                    payload=payload,
                ))
        except Exception as e:
            # A failed cache write must never fail the request — the user has
            # their forecast; persistence is our problem, not theirs.
            log.warning("Could not persist forecast run: %s", e)

    def history(self, district: str, limit: int = 10) -> List[dict]:
        district_id = DistrictLookup.id_for(district)
        if district_id is None:
            return []
        try:
            with get_session() as session:
                runs = (
                    session.query(ForecastRun)
                    .filter(ForecastRun.district_id == district_id)
                    .order_by(ForecastRun.forecast_origin.desc())
                    .limit(limit)
                    .all()
                )
                return [
                    {
                        "district": district,
                        "forecast_origin": r.forecast_origin.isoformat(),
                        "payload": r.payload,
                    }
                    for r in runs
                ]
        except Exception as e:
            log.warning("History lookup failed: %s", e)
            return []
