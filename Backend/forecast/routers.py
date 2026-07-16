"""
forecast.routers — HTTP surface. Thin: validate, delegate, return.
"""
from typing import List

from fastapi import APIRouter, Query

from forecast.schemas import (
    CurrentConditionsResponse,
    DistrictInfo,
    ForecastResponse,
    HealthResponse,
    PredictRequest,
)
from forecast.services import ForecastService

router = APIRouter(prefix="/api/v1/forecast", tags=["Forecast"])
service = ForecastService()


@router.get("/health", response_model=HealthResponse)
def health():
    """Is the model on disk and loadable?"""
    return service.health()


@router.get("/districts", response_model=List[DistrictInfo])
def list_districts():
    """The 25 districts the model was trained to serve."""
    return service.list_districts()


@router.get("/current/{district}", response_model=CurrentConditionsResponse)
async def current_conditions(district: str):
    """Live conditions right now — straight from Open-Meteo, no model.

    Everything the upstream `current` block offers: temperature, feels-like,
    humidity, rain, cloud cover, pressure, wind speed/gusts/direction, UV index,
    day/night and a condition label. Powers the "go now" district comparison.
    """
    return await service.current_conditions(district)


@router.get("/{district}", response_model=ForecastResponse)
async def forecast_district(
    district: str,
    refresh: bool = Query(default=False, description="Bypass the cache and re-run the model"),
):
    """24-hour forecast with travel advisories.

    Pulls the last 168 hours of recorded weather for the district, runs the GRU,
    and returns temperature, rainfall and humidity per hour — each with a
    GOOD / CAUTION / AVOID call — plus a daily verdict.
    """
    return await service.forecast_district(district, refresh=refresh)


@router.post("/predict", response_model=ForecastResponse)
def predict(payload: PredictRequest):
    """Inference against a caller-supplied 168-hour window."""
    return service.predict_from_records(payload.district, payload.records)
