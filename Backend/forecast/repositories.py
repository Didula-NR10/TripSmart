"""
forecast.repositories
─────────────────────
Everything that talks to the outside world: the upstream weather API, the model
artifacts on disk, and Supabase. Services depend on this; this depends on
nothing above it.
"""
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


class Rain24hRepository:
    """Holds the 24h-total rain hurdle model, its scaler, and its residual
    calibration (for range predictions). Same lazy-load discipline as
    ModelRepository: nothing loads until the first request needs it.

    compile=False on load: the model was saved with a custom weighted-BCE
    loss function that isn't registered for Keras deserialization, and
    compiling isn't needed for inference-only use anyway."""

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
        """Residual quantiles (predicted - actual, mm) from a real held-out
        validation run — used to turn one point prediction into an honest
        range instead of a falsely precise single number."""
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


# ──────────────────────────────────────────────────────────────────────────────
# 2. Upstream observations — WeatherAPI.com
# ──────────────────────────────────────────────────────────────────────────────

class WeatherRepository:
    """Fetches the 168-hour context window the model needs to see."""

    # WeatherAPI.com's free/standard plans don't expose solar irradiance
    # (W/m2) the way Open-Meteo did, so DaylightScore is approximated from the
    # UV index instead: uv/MAX_UV_INDEX while the sun's up, 0.0 at night. 11
    # is a "very high" tropical UV reading, which Sri Lanka regularly sees
    # around midday — close enough to the model's original 0-1 daylight signal
    # without inventing a fake W/m2 number.
    MAX_UV_INDEX = 11.0

    # district -> (fetched_at, flat list of WeatherAPI "hour" objects). Reusing
    # a just-fetched window across forecast/weekly (which both want "the last
    # 168 hours" for the same district within moments of each other) cuts
    # real-world call volume, since upstream data only changes once an hour.
    _window_cache: Dict[str, tuple] = {}

    async def _get_with_retry(self, path: str, params: dict) -> dict:
        """GET against WeatherAPI.com, retrying 429/5xx with backoff before giving up."""
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
                        # Not a transient failure (bad key, bad query, etc.) — retrying won't help.
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
        """The last 168 consecutive hours of RECORDED weather for a district.

        WeatherAPI.com has no single "past N days" call like Open-Meteo did.
        Today (+ tomorrow, so there's always a full 24h of WeatherAPI's own
        forecast available regardless of what time "now" is) comes from
        `forecast.json` (whose hour rows are real observations for every hour
        already elapsed, and forecast for the rest — the not-yet-elapsed rows
        get trimmed off the *context* below, but stay available via
        `get_future_forecast()`). Each of the 7 days before today needs its
        own `history.json` call, since a date *range* in one call needs a
        paid plan. All 9 calls run concurrently so this costs one
        round-trip's worth of latency, not nine sequential ones.
        """
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
            # Upstream is down/rate-limited even after retries. A slightly
            # stale window (same district, up to a cache-window old) beats a
            # hard failure — the model's own accuracy degrades far more
            # gently than "the user sees an error and can't get a forecast."
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
        """WeatherAPI's own forecast for the next `horizon` hours — reuses the
        window `fetch_context_window` already cached for this district (it's
        always called first in the request flow), no extra API call. Returns
        None if there's no cached window yet for this district."""
        cached = self._window_cache.get(district)
        if not cached:
            return None
        return self._future_from_frame(self._frame_from_hours(cached[1]), horizon)

    def _frame_from_hours(self, hours: List[dict]) -> pd.DataFrame:
        """Raw frame from WeatherAPI hour objects — deduped, sorted, feature
        columns computed. Not yet trimmed to context or future; both
        `_context_from_frame` and `_future_from_frame` slice this."""
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

        # The 9 upstream calls are independent requests, not one contiguous
        # feed — de-dupe defensively before trusting the hour boundaries.
        df = df.drop_duplicates(subset="datetime").sort_values("datetime").reset_index(drop=True)
        df["DaylightScore"] = df["DaylightScore"].clip(0.0, 1.0)
        df["Hour"] = df["datetime"].dt.hour
        df["Month"] = df["datetime"].dt.month
        return df

    def _context_from_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        """The model's 168h input: everything at or before the current hour.
        Anything at/after "now" is a WeatherAPI forecast, not an observation —
        feeding that to the model as if it already happened would quietly
        corrupt the context."""
        now = pd.Timestamp.now(tz="Asia/Colombo").tz_localize(None)
        context = df[df["datetime"] <= now].tail(settings.INPUT_WINDOW).reset_index(drop=True)

        if len(context) < settings.INPUT_WINDOW:
            raise RuntimeError(
                f"Only {len(context)} hours of observations available; "
                f"{settings.INPUT_WINDOW} are required."
            )

        # Upstream gaps would become NaNs and poison the whole window.
        return context.ffill().bfill()

    def _future_from_frame(self, df: pd.DataFrame, horizon: int) -> pd.DataFrame:
        """WeatherAPI's own forecast rows — strictly after "now", used as an
        independent second opinion for rain (see ForecastService._rain_range)."""
        now = pd.Timestamp.now(tz="Asia/Colombo").tz_localize(None)
        return df[df["datetime"] > now].head(horizon).reset_index(drop=True)

    async def fetch_current(self, district: str) -> Dict[str, Any]:
        """A live snapshot for right now — no model involved, straight from
        WeatherAPI's `current` block. Used by the district comparer's
        "current conditions" mode, where the ask is what a traveler would see
        by checking a weather app at this exact moment."""
        if district not in DISTRICT_COORDS:
            raise ValueError(f"Unknown district: '{district}'")

        coords = DISTRICT_COORDS[district]
        params = {"q": f"{coords['lat']},{coords['lon']}", "aqi": "no"}

        data = await self._get_with_retry("current.json", params)
        return data["current"]


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

        # WeatherAPI timestamps arrive naive in Asia/Colombo; observed_at is
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

    def get_stale(self, district: str) -> Optional[dict]:
        """The most recent run regardless of age — a last resort when WeatherAPI
        is unreachable even after retries. An hours-old forecast beats a hard
        error; the payload is marked `stale` so the UI can say so."""
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
