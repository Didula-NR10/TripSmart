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
