"""
forecast.schemas — the API contract. Nothing here knows about TensorFlow.
"""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class DistrictInfo(BaseModel):
    name: str
    lat: float
    lon: float


class GeocodeResult(BaseModel):
    query: str
    formatted_address: str
    lat: float
    lon: float


class ReverseGeocodeResult(BaseModel):
    lat: float
    lon: float
    place_name: str          # nearest locality/sublocality/village — short name
    formatted_address: str


class HourlyForecast(BaseModel):
    forecast_hour: int = Field(..., description="Hours ahead of the forecast origin (1-24)")
    valid_time: str = Field(..., description="Local (Asia/Colombo) timestamp this hour refers to")
    temperature_c: float
    precipitation_mm_low: float = Field(
        ..., description="Lower end of the plausible rain range for this hour — not the GRU's own regression output (see services._rain_range)"
    )
    precipitation_mm_high: float = Field(
        ..., description="Upper end of the plausible rain range for this hour; the GOOD/CAUTION/AVOID call reacts to this, not the low end"
    )
    humidity_pct: float
    advisory_level: str = Field(..., description="GOOD | CAUTION | AVOID")
    advisory_reason: str


class DailySummary(BaseModel):
    temp_min_c: float
    temp_max_c: float
    temp_avg_c: float
    rain_mm_low: float = Field(
        ..., description="Calmest hour's low-end rain estimate — mirrors temp_min_c, not a daily sum"
    )
    rain_mm_high: float = Field(
        ..., description="Wettest hour's high-end rain estimate — mirrors temp_max_c, not a daily sum"
    )
    humidity_min_pct: float
    humidity_max_pct: float
    wet_hours: int
    advisory_level: str
    verdict: str

    # ---- 24h-total rain model outlook (optional: an enrichment, absent if
    # the model artifacts aren't deployed or the prediction failed) ----
    rain_24h_probability: Optional[float] = Field(
        default=None, description="Model's probability that measurable rain falls somewhere in the next 24h"
    )
    rain_24h_total_mm: Optional[float] = Field(
        default=None, description="Point estimate of TOTAL rain over the next 24h (not a per-hour peak)"
    )
    rain_24h_total_mm_low: Optional[float] = Field(
        default=None, description="Low end of the 24h total's real 80% prediction interval"
    )
    rain_24h_total_mm_high: Optional[float] = Field(
        default=None, description="High end of the 24h total's real 80% prediction interval"
    )
    day_type: Optional[str] = Field(
        default=None,
        description="RAINY | SUNNY | OVERCAST | HOT_HUMID_STORM_RISK | MILD — from temp/humidity 24h trend + rain range, not rain amount alone",
    )
    day_type_reason: Optional[str] = None


class ForecastResponse(BaseModel):
    district: str
    forecast_origin: str = Field(..., description="UTC timestamp the model ran at")
    forecast_horizon: int = 24
    cached: bool = False
    stale: bool = Field(
        default=False,
        description="True when WeatherAPI was unreachable and this is the last known-good run, not a fresh one",
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
    rain_mm_low: float
    rain_mm_high: float
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
