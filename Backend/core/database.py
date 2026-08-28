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
    engine = create_engine(settings.SUPABASE_DB_URL, pool_pre_ping=True, pool_size=5)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
else:
    log.warning("SUPABASE_DB_URL not set — forecast caching/history disabled.")

def db_available() -> bool:
    return SessionLocal is not None

@contextmanager
def get_session() -> Iterator[Session]:
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
    if engine is None:
        return

    Base.metadata.create_all(engine)

    with engine.begin() as conn:
        for table in Base.metadata.tables:
            conn.execute(text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY'))

        conn.execute(text(
            "ALTER TABLE public.ground_reports "
            "ADD COLUMN IF NOT EXISTS author TEXT NOT NULL DEFAULT ''"
        ))
        conn.execute(text(
            "ALTER TABLE public.ground_reports "
            "ADD COLUMN IF NOT EXISTS posted_by_id UUID NULL "
            "REFERENCES public.users(id) ON DELETE SET NULL"
        ))
        conn.execute(text(
            "ALTER TABLE public.users "
            "ADD COLUMN IF NOT EXISTS avatar_url TEXT NOT NULL DEFAULT ''"
        ))
        conn.execute(text(
            "ALTER TABLE public.users "
            "ADD COLUMN IF NOT EXISTS google_sub TEXT NOT NULL DEFAULT ''"
        ))
        conn.execute(text(
            "ALTER TABLE public.travel_notes "
            "ADD COLUMN IF NOT EXISTS photo_url TEXT NOT NULL DEFAULT ''"
        ))
        conn.execute(text(
            "ALTER TABLE public.travel_notes "
            "ADD COLUMN IF NOT EXISTS journal_id UUID NULL "
            "REFERENCES public.travel_journals(id) ON DELETE CASCADE"
        ))
        conn.execute(text(
            "ALTER TABLE public.travel_notes "
            "ADD COLUMN IF NOT EXISTS page_number INTEGER NULL"
        ))

    from forecast.utils import DISTRICT_COORDS

    with get_session() as session:
        existing = {name for (name,) in session.query(District.name).all()}
        for name, coords in DISTRICT_COORDS.items():
            if name not in existing:
                session.add(District(name=name, lat=coords["lat"], lon=coords["lon"]))

    log.info("Database ready: tables created, %d districts seeded.", len(DISTRICT_COORDS))
