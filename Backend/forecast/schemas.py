"""
forecast.schemas — the API contract. Nothing here knows about TensorFlow.
"""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class DistrictInfo(BaseModel):
    name: str
    lat: float
    lon: float


class HourlyForecast(BaseModel):
    forecast_hour: int = Field(..., description="Hours ahead of the forecast origin (1-24)")
    valid_time: str = Field(..., description="Local (Asia/Colombo) timestamp this hour refers to")
    temperature_c: float
    precipitation_mm: float
    humidity_pct: float
    advisory_level: str = Field(..., description="GOOD | CAUTION | AVOID")
    advisory_reason: str


class DailySummary(BaseModel):
    temp_min_c: float
    temp_max_c: float
    temp_avg_c: float
    total_rain_mm: float
    humidity_min_pct: float
    humidity_max_pct: float
    wet_hours: int
    advisory_level: str
    verdict: str


class ForecastResponse(BaseModel):
    district: str
    forecast_origin: str = Field(..., description="UTC timestamp the model ran at")
    forecast_horizon: int = 24
    cached: bool = False
    stale: bool = Field(
        default=False,
        description="True when Open-Meteo was unreachable and this is the last known-good run, not a fresh one",
    )
    stale_reason: Optional[str] = None
    summary: DailySummary
    forecast: List[HourlyForecast]


class WeeklyDay(BaseModel):
    date: str = Field(..., description="Colombo calendar date (YYYY-MM-DD)")
    weekday: str
    hours_covered: int = Field(..., description="Predicted hours inside this date (12-24)")
    source: str = Field(..., description="gru (single-shot forecast) | gru+pattern (rollout)")
    confidence: str = Field(..., description="high | medium | low — decays with distance")
    temp_min_c: float
    temp_max_c: float
    temp_avg_c: float
    total_rain_mm: float
    humidity_min_pct: float
    humidity_max_pct: float
    wet_hours: int
    advisory_level: str
    verdict: str


class WeeklyOutlookResponse(BaseModel):
    district: str
    forecast_origin: str
    days: List[WeeklyDay]


class HourlyRecord(BaseModel):
    """One hour of raw observations — for callers supplying their own context."""
    Hour: int
    Month: int
    Temperature_C: float
    Precipitation_mm: float
    Humidity_pct: float
    CloudCover_pct: float
    WindSpeed_kmh: float
    WindGusts_kmh: float
    DaylightScore: float

    @field_validator("Hour")
    @classmethod
    def _hour(cls, v: int) -> int:
        if not 0 <= v <= 23:
            raise ValueError(f"Hour must be 0-23, got {v}")
        return v

    @field_validator("Month")
    @classmethod
    def _month(cls, v: int) -> int:
        if not 1 <= v <= 12:
            raise ValueError(f"Month must be 1-12, got {v}")
        return v


class PredictRequest(BaseModel):
    """Bring-your-own-context inference, mirroring the original /predict."""
    district: str
    records: List[HourlyRecord]

    @field_validator("records")
    @classmethod
    def _window(cls, v: list) -> list:
        if len(v) != 168:
            raise ValueError(f"Exactly 168 hourly records are required; received {len(v)}")
        return v


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    districts: int


class CurrentConditionsResponse(BaseModel):
    district: str
    observed_at: str = Field(..., description="Local (Asia/Colombo) timestamp of the reading")
    temperature_c: float
    feels_like_c: float
    humidity_pct: float
    precipitation_mm: float
    cloud_cover_pct: float
    pressure_msl_hpa: float
    wind_speed_kmh: float
    wind_gusts_kmh: float
    wind_direction_deg: float
    uv_index: float
    is_day: bool
    condition: str
