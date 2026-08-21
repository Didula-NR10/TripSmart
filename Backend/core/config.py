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
    LOGIN_MAX_ATTEMPTS: int = 5      # wrong passwords before an identifier is throttled
    LOGIN_LOCKOUT_MINUTES: int = 15  # rolling window a throttled identifier must wait out

    # ---- Email (OTP codes) — sent over HTTPS via SendGrid, not raw SMTP ----
    # Render's free tier blocks outbound traffic on the SMTP ports (25/465/587)
    # as of September 2025, so aiosmtplib-over-SMTP silently fails there no
    # matter how correct the Gmail app password is. SendGrid's Mail Send API
    # is a plain HTTPS POST (port 443), which isn't blocked.
    SENDGRID_API_KEY: str = ""
    SMTP_FROM_EMAIL: str = ""        # must be a Single Sender verified in SendGrid
    # ---- legacy SMTP fallback (kept only for local/paid-tier use) ----
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587             # 587 = STARTTLS, 465 = SSL
    SMTP_USER: str = ""              # the sending address, e.g. you@gmail.com
    SMTP_APP_PASSWORD: str = ""      # a Gmail App Password, NOT the account password

    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- Forecast model artifacts ----
    # The GRU expects 168 hours in, and emits 24 hours across 3 channels.
    MODEL_PATH: str = str(BASE_DIR / "models" / "best_checkpoint.keras")
    SCALER_PATH: str = str(BASE_DIR / "models" / "scaler.pkl")

    INPUT_WINDOW: int = 168
    TARGET_HORIZON: int = 24

    # ---- Upstream weather source (WeatherAPI.com — needs a free API key) ----
    # Open-Meteo's free tier is keyless and shared across every caller on a
    # host's egress IP, which is exactly what made it 429 under Hugging Face
    # Spaces' shared IPs. WeatherAPI.com requires a key but keys are per-account,
    # so this app's quota is no longer shared with strangers.
    WEATHERAPI_KEY: str = ""
    WEATHERAPI_BASE_URL: str = "https://api.weatherapi.com/v1"
    WEATHERAPI_TIMEOUT: int = 15
    WEATHERAPI_MAX_RETRIES: int = 3          # attempts on 429/5xx before giving up
    WEATHERAPI_RETRY_BASE_SECONDS: float = 1.5  # doubles each attempt
    # How long a raw fetched observation window is reused across endpoints
    # (forecast + weekly-outlook both want "the last 168 hours" for the same
    # district within seconds of each other) instead of re-hitting WeatherAPI.
    WEATHERAPI_WINDOW_CACHE_MINUTES: int = 15

    # ---- Mapping (Google Maps Geocoding, used by the destination search box) ----
    # The map itself (tile rendering) runs client-side in the app with its own
    # key; this one is server-side only, so it can be IP-restricted in Google
    # Cloud Console instead of being exposed to every client.
    GOOGLE_MAPS_API_KEY: str = ""

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
