import os
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

class Settings(BaseSettings):
    PROJECT_NAME: str = "Trip Smart"
    ENVIRONMENT: str = "development"

    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_DB_URL: str = ""

    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    OTP_TTL_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 5
    SESSION_DAYS: int = 30
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    GOOGLE_OAUTH_WEB_CLIENT_ID: str = ""

    SENDGRID_API_KEY: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_APP_PASSWORD: str = ""

    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    MODEL_PATH: str = str(BASE_DIR / "models" / "best_checkpoint.keras")
    SCALER_PATH: str = str(BASE_DIR / "models" / "scaler.pkl")

    INPUT_WINDOW: int = 168
    TARGET_HORIZON: int = 24

    RAIN24H_MODEL_PATH: str = str(BASE_DIR / "models" / "rain24h_model.keras")
    RAIN24H_SCALER_PATH: str = str(BASE_DIR / "models" / "rain24h_scaler.pkl")
    RAIN24H_CALIBRATION_PATH: str = str(BASE_DIR / "models" / "rain24h_calibration.json")

    WEATHERAPI_KEY: str = ""
    WEATHERAPI_BASE_URL: str = "https://api.weatherapi.com/v1"
    WEATHERAPI_TIMEOUT: int = 15
    WEATHERAPI_MAX_RETRIES: int = 3
    WEATHERAPI_RETRY_BASE_SECONDS: float = 1.5
    WEATHERAPI_WINDOW_CACHE_MINUTES: int = 15

    GOOGLE_MAPS_API_KEY: str = ""

    FORECAST_CACHE_MINUTES: int = 60

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
