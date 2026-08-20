"""
forecast.services — the business logic.

Owns the pipeline: observations → features → scale → GRU → inverse-scale →
clamp → advisory. Routers stay thin; repositories stay dumb.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import httpx
import numpy as np
import pandas as pd
from fastapi import HTTPException, status

from core.config import settings
from forecast.repositories import (
    ForecastRepository,
    ModelRepository,
    ObservationRepository,
    WeatherRepository,
)
from forecast.utils import (
    DISTRICT_COORDS,
    clamp_physical,
    daily_summary,
    engineer_features,
    hourly_advisory,
    inverse_transform_targets,
)

log = logging.getLogger("trip_smart.forecast.service")

weather_repo = WeatherRepository()
forecast_repo = ForecastRepository()
observation_repo = ObservationRepository()


class ForecastService:

    # ---- catalog ----

    def list_districts(self) -> List[Dict[str, Any]]:
        return [
            {"name": name, "lat": c["lat"], "lon": c["lon"]}
            for name, c in sorted(DISTRICT_COORDS.items())
        ]

    # ---- geocoding (destination search on the map picker) ----

    async def geocode(self, query: str) -> Dict[str, Any]:
        """Place name -> coordinates, via Google's Geocoding API, biased to
        Sri Lanka. Server-side so the key never reaches the client."""
        if not settings.GOOGLE_MAPS_API_KEY:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Geocoding is not configured (GOOGLE_MAPS_API_KEY is empty).",
            )

        params = {
            "address": query,
            "components": "country:LK",
            "key": settings.GOOGLE_MAPS_API_KEY,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://maps.googleapis.com/maps/api/geocode/json", params=params
            )
        data = response.json()

        if data.get("status") != "OK" or not data.get("results"):
            if data.get("status") == "REQUEST_DENIED":
                log.warning("Google Geocoding REQUEST_DENIED: %s", data.get("error_message"))
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY,
                    detail=f"Geocoding provider rejected the request: {data.get('error_message', 'REQUEST_DENIED')}",
                )
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f'"{query}" was not found in Sri Lanka.',
            )

        result = data["results"][0]
        location = result["geometry"]["location"]
        return {
            "query": query,
            "formatted_address": result.get("formatted_address", query),
            "lat": location["lat"],
            "lon": location["lng"],
        }

    # ---- the pipeline ----

    def _run_model(self, frame: pd.DataFrame) -> np.ndarray:
        """168 rows of raw observations → (24, 3) real-unit predictions."""
        engineered = engineer_features(frame)

        if engineered.isnull().any().any():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Gaps in the input window produced NaNs after feature engineering.",
            )

        scaler = ModelRepository.get_scaler()
        model = ModelRepository.get_model()

        scaled = scaler.transform(engineered.values).astype(np.float32)
        tensor = scaled[np.newaxis, :, :]   # (1, 168, 12)

        expected = (1, settings.INPUT_WINDOW, 12)
        if tensor.shape != expected:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Tensor shape {tensor.shape}, expected {expected}.",
            )

        raw = model.predict(tensor, verbose=0)[0].astype(np.float32)   # (24, 3)

        # Mixed-precision training can push outputs a hair outside the scaler's
        # fitted range; clip before inverting or the error is amplified.
        raw = np.clip(raw, 0.0, 1.0)

        return inverse_transform_targets(raw, scaler, settings.TARGET_HORIZON)

    # ---- rain: analog + WeatherAPI's own forecast, not the GRU's regressor ----
    #
    # A GRU trained with MSE on a mostly-dry variable learns that predicting
    # near-zero is usually "safe" — it systematically underpredicts real light
    # rain rather than being randomly noisy around it (proven: a real overnight
    # test predicted flat 0.0mm for 8 straight hours while actual rain reached
    # 1.3mm). No amount of retrying fixes a training-objective bias, so rain
    # doesn't use the GRU's own regression output at all. Instead: how much did
    # it typically rain at this exact clock hour over the past 7 real days
    # (the "analog"), cross-checked against WeatherAPI's own forecast for that
    # hour (an independently-modeled second opinion, not our regressor's
    # guess) — reported as a [low, high] range, not a single misleadingly
    # precise number. Both signals come from WeatherAPI only.

    def _analog_rain_by_hour(self, frame: pd.DataFrame) -> Dict[int, float]:
        """Average recorded rain at each clock hour, from a 168h (or shorter,
        for bring-your-own-context) window of real observations."""
        return frame.groupby("Hour")["Precipitation_mm"].mean().to_dict()

    def _rain_range(
        self,
        analog_by_hour: Dict[int, float],
        future_lookup: "Optional[pd.Series]",
        valid: datetime,
    ) -> tuple[float, float]:
        analog_rain = float(analog_by_hour.get(valid.hour, 0.0))
        wx_rain = 0.0
        if future_lookup is not None and valid in future_lookup.index:
            wx_rain = float(future_lookup.loc[valid])
        return round(min(analog_rain, wx_rain), 3), round(max(analog_rain, wx_rain), 3)

    def _assemble(
        self,
        district: str,
        real: np.ndarray,
        origin: datetime,
        last_obs_local: datetime,
        analog_by_hour: Dict[int, float],
        future_lookup: "Optional[pd.Series]" = None,
        cached: bool = False,
    ) -> dict:
        """Predictions → the shape the UI consumes, advisories included.

        The model's output hour i is the (i+1)-th hour AFTER the last observation
        it saw. Valid times are therefore anchored to that last observation in
        Asia/Colombo wall time — anchoring to UTC `now` would shift every label
        by 5½ hours, which is exactly the kind of bug users notice at 9 PM.
        """
        forecast: List[Dict[str, Any]] = []

        for i in range(settings.TARGET_HORIZON):
            # real[i][1] (the GRU's own rain channel) is deliberately unused —
            # see _rain_range's docstring above.
            temp, _, humidity = clamp_physical(
                real[i][0], real[i][1], real[i][2], hour_index=i, district=district
            )
            valid = last_obs_local + timedelta(hours=i + 1)
            rain_low, rain_high = self._rain_range(analog_by_hour, future_lookup, valid)
            # The advisory reacts to the high end — "could reach up to X mm"
            # should drive caution, not an average that might mask real risk.
            advisory = hourly_advisory(temp, rain_high, humidity)

            forecast.append({
                "forecast_hour": i + 1,
                "valid_time": valid.strftime("%Y-%m-%d %H:00"),
                "temperature_c": temp,
                "precipitation_mm_low": rain_low,
                "precipitation_mm_high": rain_high,
                "humidity_pct": humidity,
                "advisory_level": advisory["level"],
                "advisory_reason": advisory["reason"],
            })

        return {
            "district": district,
            "forecast_origin": origin.isoformat(),
            "forecast_horizon": settings.TARGET_HORIZON,
            "cached": cached,
            "summary": daily_summary(forecast),
            "forecast": forecast,
        }

    # ---- public entry points ----

    @staticmethod
    def _payload_matches_schema(payload: dict) -> bool:
        """Guards against serving a forecast_runs row saved under an older
        response shape (e.g. before rain became a [low, high] range instead
        of a single point value) — FastAPI's response_model validation would
        otherwise 500 on the mismatch. A schema change should degrade to
        "treat as a cache miss, run fresh" here, not a crash whenever a
        pre-change row is next read from the cache."""
        summary = payload.get("summary", {})
        if "rain_mm_low" not in summary or "rain_mm_high" not in summary:
            return False
        return all(
            "precipitation_mm_low" in h and "precipitation_mm_high" in h
            for h in payload.get("forecast", [])
        )

    async def forecast_district(self, district: str, refresh: bool = False) -> dict:
        """The one the UI calls: fetch context, predict, advise."""
        if district not in DISTRICT_COORDS:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Unknown district '{district}'. See GET /districts.",
            )

        if not refresh:
            cached = forecast_repo.get_fresh(district)
            if cached and self._payload_matches_schema(cached["payload"]):
                payload = cached["payload"]
                payload["cached"] = True
                return payload

        if not ModelRepository.is_ready():
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Forecast model artifacts are missing on the server.",
            )

        try:
            frame = await weather_repo.fetch_context_window(district)
        except RuntimeError as e:
            # WeatherAPI is unreachable/rate-limited even after retries. Serving
            # the last known-good forecast beats a hard error — the frontend's
            # "predict" button otherwise looks broken during a transient upstream
            # rate limit.
            stale = forecast_repo.get_stale(district)
            if stale and self._payload_matches_schema(stale["payload"]):
                payload = stale["payload"]
                payload["cached"] = True
                payload["stale"] = True
                payload["stale_reason"] = str(e)
                return payload
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(e))

        # Every fetched window tops up weather_observations — the growing
        # per-hour history behind the almanac and time-machine features.
        observation_repo.save_window(district, frame)

        real = self._run_model(frame)

        origin = datetime.now(timezone.utc)
        # The final context row is the current hour in Colombo; hour +1 of the
        # forecast is the hour after the user asked.
        last_obs_local = frame["datetime"].iloc[-1].to_pydatetime()

        analog_by_hour = self._analog_rain_by_hour(frame)
        future = weather_repo.get_future_forecast(district, settings.TARGET_HORIZON)
        future_lookup = future.set_index("datetime")["Precipitation_mm"] if future is not None and not future.empty else None

        result = self._assemble(district, real, origin, last_obs_local, analog_by_hour, future_lookup)

        forecast_repo.save(district, origin, result)
        return result

    async def weekly_outlook(self, district: str) -> dict:
        """The climate-disruption planner: a 7-day outlook where EVERY day is a
        GRU prediction, not a static climatology row.

        Hours 1-24 are the standard forecast — the model reading 168 hours of
        real observations. Beyond that the rollout is autoregressive: each
        day's predicted temperature, rain and humidity are appended to the
        input window and the model runs again on the shifted window. The three
        channels the model predicts come from the model itself; the channels
        it does not predict (cloud cover, wind, gusts, daylight) are filled
        with the past observed week's value at the same clock hour — the
        recent diurnal pattern of that exact district.

        Skill decays with distance: day 1 carries real-data momentum, later
        days increasingly reflect the model's own assumptions. Each day is
        therefore labeled with its source and an honest confidence tier
        instead of pretending day 6 is as trustworthy as tomorrow.
        """
        if district not in DISTRICT_COORDS:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Unknown district '{district}'. See GET /districts.",
            )
        if not ModelRepository.is_ready():
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Forecast model artifacts are missing on the server.",
            )

        try:
            frame = await weather_repo.fetch_context_window(district)
        except RuntimeError as e:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(e))

        observation_repo.save_window(district, frame)

        # The past week's diurnal pattern, keyed by clock hour, for the
        # channels the GRU cannot predict about its own future.
        pattern = frame.groupby("Hour")[
            ["CloudCover_%", "WindSpeed_kmh", "WindGusts_kmh", "DaylightScore"]
        ].mean()

        # WeatherAPI's own forecast only reaches ~48h out (see
        # WeatherRepository.fetch_context_window); rollout days beyond that
        # naturally fall back to the analog-only [0, analog] range inside
        # _rain_range (future_lookup simply won't have those hours).
        future = weather_repo.get_future_forecast(district, settings.TARGET_HORIZON)
        future_lookup = future.set_index("datetime")["Precipitation_mm"] if future is not None and not future.empty else None

        origin = datetime.now(timezone.utc)
        work = frame.copy()
        predicted_hours: List[Dict[str, Any]] = []

        for day in range(7):
            window = work.tail(settings.INPUT_WINDOW).reset_index(drop=True)
            real = self._run_model(window)
            last_dt = work["datetime"].iloc[-1]
            # Recomputed each day: `work` keeps growing with the model's own
            # prior predictions, so the analog reflects the latest 168h view.
            analog_by_hour = self._analog_rain_by_hour(window)

            new_rows: List[Dict[str, Any]] = []
            for i in range(settings.TARGET_HORIZON):
                # real[i][1] (the GRU's own rain channel) is deliberately
                # unused — see ForecastService._rain_range's docstring.
                temp, _, humidity = clamp_physical(
                    real[i][0], real[i][1], real[i][2], hour_index=i, district=district
                )
                valid = last_dt + pd.Timedelta(hours=i + 1)
                hour = int(valid.hour)
                rain_low, rain_high = self._rain_range(analog_by_hour, future_lookup, valid)

                predicted_hours.append({
                    "forecast_hour": day * settings.TARGET_HORIZON + i + 1,
                    "valid_time": valid.strftime("%Y-%m-%d %H:00"),
                    "temperature_c": temp,
                    "precipitation_mm_low": rain_low,
                    "precipitation_mm_high": rain_high,
                    "humidity_pct": humidity,
                })
                new_rows.append({
                    "datetime": valid,
                    "Temperature_C": temp,
                    # Feed the rollout's own memory with the range's high end
                    # (the more cautious estimate) rather than reintroducing
                    # the GRU's own biased-toward-zero rain guess.
                    "Precipitation_mm": rain_high,
                    "Humidity_%": humidity,
                    "CloudCover_%": float(pattern.loc[hour, "CloudCover_%"]),
                    "WindSpeed_kmh": float(pattern.loc[hour, "WindSpeed_kmh"]),
                    "WindGusts_kmh": float(pattern.loc[hour, "WindGusts_kmh"]),
                    "DaylightScore": float(pattern.loc[hour, "DaylightScore"]),
                    "Hour": hour,
                    "Month": int(valid.month),
                })

            work = pd.concat([work, pd.DataFrame(new_rows)], ignore_index=True)

        # Roll the 168 predicted hours up into calendar days (Colombo dates).
        # Partial edge days (< 12 hours) can't carry a fair daily verdict.
        by_date: Dict[str, List[Dict[str, Any]]] = {}
        for h in predicted_hours:
            by_date.setdefault(h["valid_time"][:10], []).append(h)

        days_out: List[Dict[str, Any]] = []
        for date_str, hours in sorted(by_date.items()):
            if len(hours) < 12:
                continue
            # A day mostly inside the first 24 predicted hours is the real
            # single-shot GRU forecast; later days are rollout territory.
            median_ahead = sorted(x["forecast_hour"] for x in hours)[len(hours) // 2]
            if median_ahead <= 24:
                source, confidence = "gru", "high"
            elif median_ahead <= 72:
                source, confidence = "gru+pattern", "medium"
            else:
                source, confidence = "gru+pattern", "low"

            days_out.append({
                "date": date_str,
                "weekday": datetime.strptime(date_str, "%Y-%m-%d").strftime("%A"),
                "hours_covered": len(hours),
                "source": source,
                "confidence": confidence,
                **daily_summary(hours),
            })

        return {
            "district": district,
            "forecast_origin": origin.isoformat(),
            "days": days_out[:7],
        }

    def predict_from_records(self, district: str, records: list) -> dict:
        """Bring-your-own-context inference — the original /predict contract."""
        rows = [{
            "Hour": r.Hour,
            "Month": r.Month,
            "Temperature_C": r.Temperature_C,
            "Precipitation_mm": r.Precipitation_mm,
            "Humidity_%": r.Humidity_pct,
            "CloudCover_%": r.CloudCover_pct,
            "WindSpeed_kmh": r.WindSpeed_kmh,
            "WindGusts_kmh": r.WindGusts_kmh,
            "DaylightScore": r.DaylightScore,
        } for r in records]
        frame = pd.DataFrame(rows)

        real = self._run_model(frame)
        # Caller-supplied records carry no timestamps; anchor to the current
        # Colombo hour, which is what the last record is expected to be.
        now_lk = datetime.now(ZoneInfo("Asia/Colombo")).replace(
            minute=0, second=0, microsecond=0, tzinfo=None
        )
        # No live WeatherAPI fetch here (caller supplied the context), so rain
        # is analog-only — _rain_range degrades to [0, analog] with no
        # future_lookup, still better than trusting the GRU's zero-biased guess.
        analog_by_hour = self._analog_rain_by_hour(frame)
        return self._assemble(district, real, datetime.now(timezone.utc), now_lk, analog_by_hour)

    async def current_conditions(self, district: str) -> dict:
        """A live WeatherAPI snapshot for `district` — no model, just what the
        sky is doing right now. Powers the "current conditions" comparer mode."""
        if district not in DISTRICT_COORDS:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Unknown district '{district}'. See GET /districts.",
            )
        try:
            current = await weather_repo.fetch_current(district)
        except RuntimeError as e:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(e))

        return {
            "district": district,
            "observed_at": current["last_updated"],
            "temperature_c": current["temp_c"],
            "feels_like_c": current["feelslike_c"],
            "humidity_pct": current["humidity"],
            "precipitation_mm": current["precip_mm"],
            "cloud_cover_pct": current["cloud"],
            "pressure_msl_hpa": current["pressure_mb"],
            "wind_speed_kmh": current["wind_kph"],
            "wind_gusts_kmh": current["gust_kph"],
            "wind_direction_deg": current["wind_degree"],
            "uv_index": current["uv"],
            "is_day": bool(current["is_day"]),
            "condition": current["condition"]["text"],
        }

    def history(self, district: str, limit: int = 10) -> List[dict]:
        return forecast_repo.history(district, limit)

    def health(self) -> dict:
        return {
            "status": "ok" if ModelRepository.is_ready() else "degraded",
            "model_loaded": ModelRepository.is_ready(),
            "districts": len(DISTRICT_COORDS),
        }
