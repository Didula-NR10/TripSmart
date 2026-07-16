"""
core.models — the database schema, as code.

SQLAlchemy creates these tables in Supabase on startup (see core.database.init_db),
so there is no SQL to paste into the dashboard. Column types and constraints
mirror the model's feature contract exactly.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


UTC_NOW = text("timezone('utc'::text, now())")


class District(Base):
    """The 25 administrative districts the model was trained on."""

    __tablename__ = "districts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    lat: Mapped[float] = mapped_column(Numeric(8, 5), nullable=False)
    lon: Mapped[float] = mapped_column(Numeric(8, 5), nullable=False)
    created_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=UTC_NOW, nullable=False
    )


class WeatherObservation(Base):
    """One hour of recorded weather for a district — the raw numeric attributes
    the model's feature engineering requires. Every forecast run tops this table
    up with the 168-hour context window it fetched."""

    __tablename__ = "weather_observations"
    __table_args__ = (
        # A district can only have one unique record per hour.
        UniqueConstraint("district_id", "observed_at", name="uq_district_hour"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    district_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("districts.id", ondelete="CASCADE"),
        nullable=False,
    )
    observed_at = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    temperature_c = mapped_column(Numeric(5, 2), nullable=False)
    precipitation_mm = mapped_column(Numeric(6, 3), nullable=False)
    humidity_pct = mapped_column(Numeric(4, 1), nullable=False)
    cloud_cover_pct = mapped_column(Numeric(4, 1), nullable=False)
    wind_speed_kmh = mapped_column(Numeric(5, 2), nullable=False)
    wind_gusts_kmh = mapped_column(Numeric(5, 2), nullable=False)
    daylight_score = mapped_column(Numeric(5, 4), nullable=False)

    created_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=UTC_NOW, nullable=False
    )


class GroundReport(Base):
    """A traveller's live report of conditions on the ground. Reports are
    ephemeral by design: anything older than 24 hours is purged from the
    database — yesterday's trail mud is not information, it's noise."""

    __tablename__ = "ground_reports"
    __table_args__ = (
        # The list query is always (district?, newest first); expiry scans created_at.
        Index("ground_reports_district_created_idx", "district_id", "created_at"),
        Index("ground_reports_created_idx", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    district_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("districts.id", ondelete="CASCADE"),
        nullable=False,
    )
    location: Mapped[str] = mapped_column(Text, nullable=False)   # free text: "Ella Rock trail"
    title: Mapped[str] = mapped_column(Text, nullable=False)      # the main purpose, one line
    body: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=UTC_NOW, nullable=False
    )


class ForecastRun(Base):
    """A completed model run. Serving repeats from here skips the GRU."""

    __tablename__ = "forecast_runs"
    __table_args__ = (
        # Every cache lookup is (district, most recent) — index for exactly that.
        Index("forecast_runs_district_origin_idx", "district_id", "forecast_origin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    district_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("districts.id", ondelete="CASCADE"),
        nullable=False,
    )
    forecast_origin = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    payload = mapped_column(JSONB, nullable=False)
    created_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=UTC_NOW, nullable=False
    )
