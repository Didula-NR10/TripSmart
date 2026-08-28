from __future__ import annotations

from pathlib import Path

INPUT_WINDOW = 168
TARGET_HORIZON = 24

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
    "Pressure_hPa": ["pressure_hpa", "pressure_msl", "mean_sea_level_pressure", "pressure"],
    "DewPoint_C": ["dewpoint_c", "dewpoint_2m", "dew_point", "dew_point_c"],
}

REQUIRED_RAW_COLUMNS = [
    "datetime", "Temperature_C", "Precipitation_mm", "Humidity_%",
    "CloudCover_%", "WindSpeed_kmh", "WindGusts_kmh", "radiation",
]
OPTIONAL_RAW_COLUMNS = ["district", "Pressure_hPa", "DewPoint_C"]

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

EXTENDED_FEATURE_COLS: list[str] = [
    "Pressure_hPa", "DewPoint_C",
    "Temp_lag_24h", "Temp_lag_168h",
    "Humidity_lag_24h", "Humidity_lag_168h",
    "Rain_sum_24h", "Rain_sum_72h",
    "Temp_roll_mean_24h", "Temp_roll_std_24h",
    "Humidity_roll_mean_24h",
    "CloudCover_roll_mean_24h",
]

TARGET_COLS: list[str] = ["Temperature_C", "Precipitation_mm", "Humidity_%"]

MAX_RADIATION_WM2 = 1000.0

TRAIN_FRACTION = 0.70
VAL_FRACTION = 0.15
TEST_FRACTION = 0.15

ALTERNATE_MODELS_DIR = Path(__file__).resolve().parent.parent
EXTRA_DIR = ALTERNATE_MODELS_DIR.parent
DATA_DIR = ALTERNATE_MODELS_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
