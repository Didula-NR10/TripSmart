import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth.routers import router as auth_router
from core.config import settings
from core.database import init_db
from forecast.routers import router as forecast_router
from notes.journal_router import router as journal_router
from notes.routers import router as notes_router
from reports.routers import router as reports_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

log = logging.getLogger("trip_smart.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception as e:
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
    allow_origin_regex=(
        r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
        if settings.ENVIRONMENT == "development"
        else None
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(forecast_router)
app.include_router(notes_router)
app.include_router(journal_router)
app.include_router(reports_router)

@app.get("/", tags=["Health"])
def root():
    return {"service": settings.PROJECT_NAME, "status": "running", "docs": "/docs"}
