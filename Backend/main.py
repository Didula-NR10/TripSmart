"""
Trip Smart — API entrypoint.

Layered: routers → services → repositories → (model | Open-Meteo | Supabase).
Each module (forecast, profile, almanac, suggestions, advisory) plugs in here
and nowhere else.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import init_db
from forecast.routers import router as forecast_router
from reports.routers import router as reports_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

log = logging.getLogger("trip_smart.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tables are created in Supabase here, on boot — never by hand in the dashboard.
    try:
        init_db()
    except Exception as e:
        # A broken DB must not stop the API: forecasting itself is stateless.
        log.error("Database initialisation failed (continuing without persistence): %s", e)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Atmospheric forecasting and travel advisories for Sri Lanka.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # In development, Expo web may serve from any localhost port (8081, 8099,
    # 19006, ...) — accept them all so a port change never breaks the app.
    # Production still relies on the explicit ALLOWED_ORIGINS list alone.
    allow_origin_regex=(
        r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
        if settings.ENVIRONMENT == "development"
        else None
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(forecast_router)
app.include_router(reports_router)
# app.include_router(profile_router)
# app.include_router(almanac_router)
# app.include_router(suggestions_router)
# app.include_router(advisory_router)


@app.get("/", tags=["Health"])
def root():
    return {"service": settings.PROJECT_NAME, "status": "running", "docs": "/docs"}
