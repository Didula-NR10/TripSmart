"""
Application configuration — one source of truth, read from the environment.
"""
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

    # ---- Supabase ----
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_DB_URL: str = ""

    # ---- Security ----
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ---- Auth (signup / login / OTP email) ----
    OTP_TTL_MINUTES: int = 10        # emailed codes die after this
    OTP_MAX_ATTEMPTS: int = 5        # wrong guesses before the code is void
    SESSION_DAYS: int = 30           # bearer-token lifetime

    # ---- SMTP — used to email OTP codes (Gmail app password works) ----
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587             # 587 = STARTTLS, 465 = SSL
    SMTP_USER: str = ""              # the sending address, e.g. you@gmail.com
    SMTP_APP_PASSWORD: str = ""      # a Gmail App Password, NOT the account password
    SMTP_FROM_EMAIL: str = ""        # optional display-from; defaults to SMTP_USER

    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- Forecast model artifacts ----
    # The GRU expects 168 hours in, and emits 24 hours across 3 channels.
    MODEL_PATH: str = str(BASE_DIR / "models" / "best_checkpoint.keras")
    SCALER_PATH: str = str(BASE_DIR / "models" / "scaler.pkl")

    INPUT_WINDOW: int = 168
    TARGET_HORIZON: int = 24

    # ---- Upstream weather source (no API key required) ----
    OPEN_METEO_URL: str = "https://api.open-meteo.com/v1/forecast"
    OPEN_METEO_TIMEOUT: int = 15

    # A forecast run is reused for this long rather than re-running the model.
    # The upstream data is hourly, so anything finer buys nothing.
    FORECAST_CACHE_MINUTES: int = 60

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=("settings_",),   # allow MODEL_PATH without warnings
    )

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
