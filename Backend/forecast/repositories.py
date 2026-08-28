from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import httpx
import numpy as np
import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.config import settings
from core.database import db_available, get_session
from core.models import District, ForecastRun, WeatherObservation
from forecast.utils import DISTRICT_COORDS

log = logging.getLogger("trip_smart.forecast.repo")

class ModelRepository:

    _model = None
    _scaler = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            import tensorflow as tf

            path = settings.MODEL_PATH
            log.info("Loading GRU forecaster from %s ...", path)
            cls._model = tf.keras.models.load_model(path)

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

class Rain24hRepository:

    _model = None
    _scaler = None
    _calibration = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            import tensorflow as tf

            log.info("Loading 24h rain model from %s ...", settings.RAIN24H_MODEL_PATH)
            cls._model = tf.keras.models.load_model(settings.RAIN24H_MODEL_PATH, compile=False)

            import numpy as np

            from forecast.rain24h import INPUT_WINDOW, N_FEATURES

            dummy = np.zeros((1, INPUT_WINDOW, N_FEATURES), dtype=np.float32)
            cls._model.predict(dummy, verbose=0)
            log.info("24h rain model ready. Input shape: %s", cls._model.input_shape)
        return cls._model

    @classmethod
    def get_scaler(cls):
        if cls._scaler is None:
            import joblib

            from forecast.rain24h import N_FEATURES

            log.info("Loading 24h rain scaler from %s ...", settings.RAIN24H_SCALER_PATH)
            scaler = joblib.load(settings.RAIN24H_SCALER_PATH)
            if scaler.n_features_in_ != N_FEATURES:
                raise ValueError(
                    f"24h rain scaler was fitted on {scaler.n_features_in_} features, "
                    f"but rain24h.FEATURE_COLS defines {N_FEATURES}. Artifacts and code "
                    "are out of sync — refusing to serve wrong numbers."
                )
            cls._scaler = scaler
        return cls._scaler

    @classmethod
    def get_calibration(cls) -> dict:
        if cls._calibration is None:
            import json

            with open(settings.RAIN24H_CALIBRATION_PATH) as fh:
                cls._calibration = json.load(fh)
        return cls._calibration

    @classmethod
    def is_ready(cls) -> bool:
        import os

        return (
            os.path.exists(settings.RAIN24H_MODEL_PATH)
            and os.path.exists(settings.RAIN24H_SCALER_PATH)
            and os.path.exists(settings.RAIN24H_CALIBRATION_PATH)
        )

class WeatherRepository:

    MAX_UV_INDEX = 11.0

    _window_cache: Dict[str, tuple] = {}

    async def _get_with_retry(self, path: str, params: dict) -> dict:
        url = f"{settings.WEATHERAPI_BASE_URL}/{path}"
        params = {**params, "key": settings.WEATHERAPI_KEY}
        delay = settings.WEATHERAPI_RETRY_BASE_SECONDS
        last_error: Optional[str] = None

        async with httpx.AsyncClient(timeout=settings.WEATHERAPI_TIMEOUT) as client:
            for attempt in range(settings.WEATHERAPI_MAX_RETRIES):
                try:
                    response = await client.get(url, params=params)
                except httpx.TimeoutException:
                    last_error = "WeatherAPI request timed out"
                    wait = delay
                else:
                    if response.status_code == 200:
                        return response.json()

                    last_error = f"WeatherAPI returned {response.status_code}: {response.text[:200]}"
                    if response.status_code != 429 and response.status_code < 500:
                        raise RuntimeError(last_error)

                    retry_after = response.headers.get("retry-after")
                    wait = float(retry_after) if retry_after and retry_after.strip().isdigit() else delay

                if attempt < settings.WEATHERAPI_MAX_RETRIES - 1:
                    log.warning(
                        "WeatherAPI attempt %d/%d failed (%s) — retrying in %.1fs",
                        attempt + 1, settings.WEATHERAPI_MAX_RETRIES, last_error, wait,
                    )
                    await asyncio.sleep(wait)
                    delay *= 2

        raise RuntimeError(last_error or "WeatherAPI request failed")

    async def fetch_context_window(self, district: str) -> pd.DataFrame:
        if district not in DISTRICT_COORDS:
            raise ValueError(f"Unknown district: '{district}'")

        cached = self._window_cache.get(district)
        if cached:
            fetched_at, hours = cached
            age = datetime.now(timezone.utc) - fetched_at
            if age < timedelta(minutes=settings.WEATHERAPI_WINDOW_CACHE_MINUTES):
                return self._context_from_frame(self._frame_from_hours(hours))

        coords = DISTRICT_COORDS[district]
        q = f"{coords['lat']},{coords['lon']}"
        today = datetime.now(ZoneInfo("Asia/Colombo")).date()

        try:
            payloads = await asyncio.gather(
                self._get_with_retry("forecast.json", {"q": q, "days": 2, "aqi": "no", "alerts": "no"}),
                *[
                    self._get_with_retry("history.json", {"q": q, "dt": (today - timedelta(days=d)).isoformat()})
                    for d in range(1, 8)
                ],
            )
        except RuntimeError as e:
            if cached:
                log.warning("WeatherAPI unavailable for %s; serving stale window from %s", district, cached[0])
                return self._context_from_frame(self._frame_from_hours(cached[1]))
            raise

        hours: List[dict] = []
        for payload in payloads:
            for forecastday in payload["forecast"]["forecastday"]:
                hours.extend(forecastday["hour"])

        self._window_cache[district] = (datetime.now(timezone.utc), hours)
        return self._context_from_frame(self._frame_from_hours(hours))

    def get_future_forecast(self, district: str, horizon: int) -> Optional[pd.DataFrame]:
        cached = self._window_cache.get(district)
        if not cached:
            return None
        return self._future_from_frame(self._frame_from_hours(cached[1]), horizon)

    def _frame_from_hours(self, hours: List[dict]) -> pd.DataFrame:
        df = pd.DataFrame({
            "datetime": pd.to_datetime([h["time"] for h in hours]),
            "Temperature_C": [h["temp_c"] for h in hours],
            "Precipitation_mm": [h["precip_mm"] for h in hours],
            "Humidity_%": [h["humidity"] for h in hours],
            "CloudCover_%": [h["cloud"] for h in hours],
            "WindSpeed_kmh": [h["wind_kph"] for h in hours],
            "WindGusts_kmh": [h["gust_kph"] for h in hours],
            "DaylightScore": [
                (h["uv"] / self.MAX_UV_INDEX) if h.get("is_day") else 0.0 for h in hours
            ],
        })

        df = df.drop_duplicates(subset="datetime").sort_values("datetime").reset_index(drop=True)
        df["DaylightScore"] = df["DaylightScore"].clip(0.0, 1.0)
        df["Hour"] = df["datetime"].dt.hour
        df["Month"] = df["datetime"].dt.month
        return df

    def _context_from_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        now = pd.Timestamp.now(tz="Asia/Colombo").tz_localize(None)
        context = df[df["datetime"] <= now].tail(settings.INPUT_WINDOW).reset_index(drop=True)

        if len(context) < settings.INPUT_WINDOW:
            raise RuntimeError(
                f"Only {len(context)} hours of observations available; "
                f"{settings.INPUT_WINDOW} are required."
            )

        return context.ffill().bfill()

    def _future_from_frame(self, df: pd.DataFrame, horizon: int) -> pd.DataFrame:
        now = pd.Timestamp.now(tz="Asia/Colombo").tz_localize(None)
        return df[df["datetime"] > now].head(horizon).reset_index(drop=True)

    async def fetch_current(self, district: str) -> Dict[str, Any]:
        if district not in DISTRICT_COORDS:
            raise ValueError(f"Unknown district: '{district}'")

        coords = DISTRICT_COORDS[district]
        params = {"q": f"{coords['lat']},{coords['lon']}", "aqi": "no"}

        data = await self._get_with_retry("current.json", params)
        return data["current"]

class DistrictLookup:

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

    def save_window(self, district: str, frame: pd.DataFrame) -> None:
        district_id = DistrictLookup.id_for(district)
        if district_id is None:
            return

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
            log.warning("Could not persist observations for %s: %s", district, e)

class ForecastRepository:

    def get_fresh(self, district: str) -> Optional[dict]:
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

    def get_stale(self, district: str) -> Optional[dict]:
        district_id = DistrictLookup.id_for(district)
        if district_id is None:
            return None
        try:
            with get_session() as session:
                run = (
                    session.query(ForecastRun)
                    .filter(ForecastRun.district_id == district_id)
                    .order_by(ForecastRun.forecast_origin.desc())
                    .first()
                )
                return {"payload": run.payload} if run else None
        except Exception as e:
            log.warning("Stale-forecast lookup failed: %s", e)
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
