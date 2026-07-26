"""
alternate_models/common/config.py
────────────────────────────────────
Shared constants for every candidate model in alternate_models/. Mirrors the
production contract in Backend/forecast/utils.py + core/config.py so a
trained model here is a drop-in replacement for best_checkpoint.keras +
scaler.pkl (same 168h input window, same 24h output horizon, same 3
targets), while allowing an OPTIONAL richer feature set for the models that
can use it (LightGBM especially benefits from more engineered features than
the 12-feature contract the production GRU uses).

Column names: nobody knows the exact header names in the xlsx you'll
provide yet, so RAW_COLUMN_ALIASES lists every name Open-Meteo (and common
export tools) use for each field. resolve_columns() in data_prep.py uses
this to rename whatever your file has onto the canonical names below —
you don't need to pre-edit the spreadsheet.
"""
from __future__ import annotations

from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Sequence contract — MUST match Backend/core/config.py exactly. Changing
# these means the resulting model can no longer replace best_checkpoint.keras
# without also changing Backend/forecast/repositories.py & routers.
# ──────────────────────────────────────────────────────────────────────────────
INPUT_WINDOW = 168   # hours of history the model reads
TARGET_HORIZON = 24  # hours ahead it predicts

# ──────────────────────────────────────────────────────────────────────────────
# Canonical column names used everywhere downstream, and the aliases each one
# is recognized under in a raw xlsx/csv export. Matching is case-insensitive
# and ignores spaces/underscores, so "Wind Speed (km/h)" matches "windspeed_10m".
# ──────────────────────────────────────────────────────────────────────────────
RAW_COLUMN_ALIASES: dict[str, list[str]] = {
    "datetime": ["datetime", "date", "time", "timestamp", "observed_at"],
    "district": ["district", "location", "city", "station", "region"],
    "Temperature_C": ["temperature_c", "temperature_2m", "temperature", "temp_c", "temp"],
    "Precipitation_mm": ["precipitation_mm", "precipitation", "rain_mm", "rain", "rainfall"],
    "Humidity_%": ["humidity_%", "humidity_pct", "relativehumidity_2m", "relative_humidity_2m", "humidity"],
    "CloudCover_%": ["cloudcover_%", "cloudcover", "cloud_cover", "cloud_cover_%"],
    "WindSpeed_kmh": ["windspeed_kmh", "windspeed_10m", "wind_speed_10m", "wind_speed", "windspeed"],
    "WindGusts_kmh": ["windgusts_kmh", "windgusts_10m", "wind_gusts_10m", "wind_gusts", "windgusts"],
    "radiation": ["radiation", "direct_radiation", "solar_radiation", "shortwave_radiation"],
    # Optional extras — used only if present, to enrich features beyond the
    # production 12-feature contract (LightGBM in particular benefits).
    "Pressure_hPa": ["pressure_hpa", "pressure_msl", "mean_sea_level_pressure", "pressure"],
    "DewPoint_C": ["dewpoint_c", "dewpoint_2m", "dew_point", "dew_point_c"],
}

REQUIRED_RAW_COLUMNS = [
    "datetime", "Temperature_C", "Precipitation_mm", "Humidity_%",
    "CloudCover_%", "WindSpeed_kmh", "WindGusts_kmh", "radiation",
]
OPTIONAL_RAW_COLUMNS = ["district", "Pressure_hPa", "DewPoint_C"]

# ──────────────────────────────────────────────────────────────────────────────
# The production 12-feature contract — every model here supports at least
# this (so it can be swapped straight into Backend/forecast/utils.py). Order
# matters for the deep models' input tensor; LightGBM doesn't care about
# order but keeps it anyway for consistency.
# ──────────────────────────────────────────────────────────────────────────────
BASE_FEATURE_COLS: list[str] = [
    "Temperature_C",
    "Precipitation_mm",
    "Humidity_%",
    "CloudCover_%",
    "WindSpeed_kmh",
    "WindGusts_kmh",
    "DaylightScore",
    "Hour_sin",
    "Hour_cos",
    "Month_sin",
    "Month_cos",
    "Temp_Change_3h",
]

# Extra engineered features available when ENABLE_EXTENDED_FEATURES = True in
# a model's train.py. Mostly lag/rolling statistics — cheap to compute, and
# give tree models (which have no built-in memory of the past, unlike a GRU)
# a fighting chance at capturing daily/weekly persistence explicitly.
EXTENDED_FEATURE_COLS: list[str] = [
    "Pressure_hPa", "DewPoint_C",             # only added if present in the source data
    "Temp_lag_24h", "Temp_lag_168h",
    "Humidity_lag_24h", "Humidity_lag_168h",
    "Rain_sum_24h", "Rain_sum_72h",
    "Temp_roll_mean_24h", "Temp_roll_std_24h",
    "Humidity_roll_mean_24h",
    "CloudCover_roll_mean_24h",
]

TARGET_COLS: list[str] = ["Temperature_C", "Precipitation_mm", "Humidity_%"]

MAX_RADIATION_WM2 = 1000.0  # Sri Lanka peak direct radiation, same as production

# ──────────────────────────────────────────────────────────────────────────────
# Chronological split — NEVER split time series data randomly (it leaks the
# future into the training set through overlapping windows). Ratios apply to
# the full date range, oldest-to-newest.
# ──────────────────────────────────────────────────────────────────────────────
TRAIN_FRACTION = 0.70
VAL_FRACTION = 0.15
TEST_FRACTION = 0.15  # implied remainder

ALTERNATE_MODELS_DIR = Path(__file__).resolve().parent.parent
EXTRA_DIR = ALTERNATE_MODELS_DIR.parent
DATA_DIR = ALTERNATE_MODELS_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
