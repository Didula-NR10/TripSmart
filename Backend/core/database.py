"""
core.database — the Supabase Postgres connection.

Supabase is plain Postgres underneath, so the backend connects directly with
SQLAlchemy using SUPABASE_DB_URL and creates its own tables on startup
(init_db, called from main.py's lifespan). Nothing is ever pasted into the
SQL editor by hand.

Repositories talk to get_session(); nothing else should.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import settings
from core.models import Base, District

log = logging.getLogger("trip_smart.database")

engine: Optional[Engine] = None
SessionLocal: Optional[sessionmaker] = None

if settings.SUPABASE_DB_URL:
    # pool_pre_ping revalidates pooled connections — Supabase's pooler drops
    # idle ones, and a stale socket would otherwise surface as a 500.
    engine = create_engine(settings.SUPABASE_DB_URL, pool_pre_ping=True, pool_size=5)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
else:
    # The forecast engine is stateless — it can serve predictions with no
    # database at all. Persistence (caching, history, observations) switches off.
    log.warning("SUPABASE_DB_URL not set — forecast caching/history disabled.")


def db_available() -> bool:
    return SessionLocal is not None


@contextmanager
def get_session() -> Iterator[Session]:
    """One unit of work. Commits on success, rolls back on any exception."""
    if SessionLocal is None:
        raise RuntimeError("Database is not configured (SUPABASE_DB_URL is empty).")
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create every table the app needs and seed the district catalog.

    Runs at startup and is idempotent: create_all skips tables that already
    exist, and the seed inserts skip districts already present.
    """
    if engine is None:
        return

    Base.metadata.create_all(engine)

    # These tables belong to the backend alone. Enabling row level security
    # locks them away from Supabase's public REST API (anon key); the backend
    # itself connects as the table owner, which RLS does not restrict.
    with engine.begin() as conn:
        for table in Base.metadata.tables:
            conn.execute(text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY'))

    # Seed the 25 districts the model serves. Imported here, not at module
    # top, to keep core free of forecast-package imports at load time.
    from forecast.utils import DISTRICT_COORDS

    with get_session() as session:
        existing = {name for (name,) in session.query(District.name).all()}
        for name, coords in DISTRICT_COORDS.items():
            if name not in existing:
                session.add(District(name=name, lat=coords["lat"], lon=coords["lon"]))

    log.info("Database ready: tables created, %d districts seeded.", len(DISTRICT_COORDS))
