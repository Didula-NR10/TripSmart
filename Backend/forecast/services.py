"""
forecast.services — the business logic.

Owns the pipeline: observations → features → scale → GRU → inverse-scale →
clamp → advisory. Routers stay thin; repositories stay dumb.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

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
    weather_condition_text,
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

    def _assemble(
        self,
        district: str,
        real: np.ndarray,
        origin: datetime,
        last_obs_local: datetime,
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
            temp, rain, humidity = clamp_physical(real[i][0], real[i][1], real[i][2])
            valid = last_obs_local + timedelta(hours=i + 1)
            advisory = hourly_advisory(temp, rain, humidity)

            forecast.append({
                "forecast_hour": i + 1,
                "valid_time": valid.strftime("%Y-%m-%d %H:00"),
                "temperature_c": temp,
                "precipitation_mm": rain,
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

    async def forecast_district(self, district: str, refresh: bool = False) -> dict:
        """The one the UI calls: fetch context, predict, advise."""
        if district not in DISTRICT_COORDS:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Unknown district '{district}'. See GET /districts.",
            )

        if not refresh:
            cached = forecast_repo.get_fresh(district)
            if cached:
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
            # Open-Meteo is unreachable/rate-limited even after retries. Serving
            # the last known-good forecast beats a hard error — the frontend's
            # "predict" button otherwise looks broken during a transient upstream
            # rate limit, which is the common case on shared-IP hosts.
            stale = forecast_repo.get_stale(district)
            if stale:
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
        result = self._assemble(district, real, origin, last_obs_local)

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

        origin = datetime.now(timezone.utc)
        work = frame.copy()
        predicted_hours: List[Dict[str, Any]] = []

        for day in range(7):
            window = work.tail(settings.INPUT_WINDOW).reset_index(drop=True)
            real = self._run_model(window)
            last_dt = work["datetime"].iloc[-1]

            new_rows: List[Dict[str, Any]] = []
            for i in range(settings.TARGET_HORIZON):
                temp, rain, humidity = clamp_physical(real[i][0], real[i][1], real[i][2])
                valid = last_dt + pd.Timedelta(hours=i + 1)
                hour = int(valid.hour)

                predicted_hours.append({
                    "forecast_hour": day * settings.TARGET_HORIZON + i + 1,
                    "valid_time": valid.strftime("%Y-%m-%d %H:00"),
                    "temperature_c": temp,
                    "precipitation_mm": rain,
                    "humidity_pct": humidity,
                })
                new_rows.append({
                    "datetime": valid,
                    "Temperature_C": temp,
                    "Precipitation_mm": rain,
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

        real = self._run_model(pd.DataFrame(rows))
        # Caller-supplied records carry no timestamps; anchor to the current
        # Colombo hour, which is what the last record is expected to be.
        now_lk = datetime.now(ZoneInfo("Asia/Colombo")).replace(
            minute=0, second=0, microsecond=0, tzinfo=None
        )
        return self._assemble(district, real, datetime.now(timezone.utc), now_lk)

    async def current_conditions(self, district: str) -> dict:
        """A live Open-Meteo snapshot for `district` — no model, just what the
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
            "observed_at": current["time"],
            "temperature_c": current["temperature_2m"],
            "feels_like_c": current["apparent_temperature"],
            "humidity_pct": current["relative_humidity_2m"],
            "precipitation_mm": current["precipitation"],
            "cloud_cover_pct": current["cloud_cover"],
            "pressure_msl_hpa": current["pressure_msl"],
            "wind_speed_kmh": current["wind_speed_10m"],
            "wind_gusts_kmh": current["wind_gusts_10m"],
            "wind_direction_deg": current["wind_direction_10m"],
            "uv_index": current["uv_index"],
            "is_day": bool(current["is_day"]),
            "condition": weather_condition_text(current["weather_code"]),
        }

    def history(self, district: str, limit: int = 10) -> List[dict]:
        return forecast_repo.history(district, limit)

    def health(self) -> dict:
        return {
            "status": "ok" if ModelRepository.is_ready() else "degraded",
            "model_loaded": ModelRepository.is_ready(),
            "districts": len(DISTRICT_COORDS),
        }
