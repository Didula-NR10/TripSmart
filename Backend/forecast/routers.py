from typing import List

from fastapi import APIRouter, Query

from forecast.schemas import (
    CurrentConditionsResponse,
    DistrictInfo,
    ForecastResponse,
    GeocodeResult,
    HealthResponse,
    PredictRequest,
    ReverseGeocodeResult,
    WeeklyOutlookResponse,
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
    """Live conditions right now — straight from WeatherAPI, no model.

    Everything the upstream `current` block offers: temperature, feels-like,
    humidity, rain, cloud cover, pressure, wind speed/gusts/direction, UV index,
    day/night and a condition label. Powers the "go now" district comparison.
    """
    return await service.current_conditions(district)

@router.get("/weekly/{district}", response_model=WeeklyOutlookResponse)
async def weekly_outlook(district: str):
    """7-day planner outlook — every day is a GRU prediction.

    Day 1 is the standard single-shot forecast from 168 hours of observations.
    Later days are autoregressive: the model's own predictions extend its input
    window, with unpredicted channels (cloud, wind, daylight) filled from the
    past week's same-hour pattern. Confidence is labeled and decays with distance.
    """
    return await service.weekly_outlook(district)

@router.get("/geocode", response_model=GeocodeResult)
async def geocode(q: str = Query(..., min_length=1, description="Place name, e.g. 'Ella'")):
    """Place name -> coordinates for the map picker's search box.

    Proxied server-side through Google's Geocoding API so the key stays out
    of the client and can be IP-restricted instead of exposed to every app
    install.
    """
    return await service.geocode(q)

@router.get("/reverse-geocode", response_model=ReverseGeocodeResult)
async def reverse_geocode(
    lat: float = Query(..., description="Latitude of the dropped pin"),
    lon: float = Query(..., description="Longitude of the dropped pin"),
):
    """Coordinates -> nearest town/city/village name.

    Backs the Ground Reports form's map picker: drop a pin, get back a real
    place name to prefill the 'where exactly' field with, instead of raw
    coordinates.
    """
    return await service.reverse_geocode(lat, lon)

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
