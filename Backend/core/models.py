"""
core.models — the database schema, as code.

SQLAlchemy creates these tables in Supabase on startup (see core.database.init_db),
so there is no SQL to paste into the dashboard. Column types and constraints
mirror the model's feature contract exactly.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
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
    author: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=UTC_NOW, nullable=False
    )


class User(Base):
    """A registered traveller. Passwords are stored only as PBKDF2 hashes;
    the account activates once the emailed OTP is confirmed."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)  # stored lowercase
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)     # stored lowercase
    country: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    avatar_url: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=UTC_NOW, nullable=False
    )
    updated_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=UTC_NOW, nullable=False
    )
    last_login_at = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class EmailOtp(Base):
    """A one-time code emailed for signup verification or a password reset.
    Codes expire quickly, allow limited attempts, and are deleted on use."""

    __tablename__ = "email_otps"
    __table_args__ = (
        Index("email_otps_email_purpose_idx", "email", "purpose"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)          # 6 digits
    purpose: Mapped[str] = mapped_column(Text, nullable=False)       # 'signup' | 'reset'
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    expires_at = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=UTC_NOW, nullable=False
    )


class AuthToken(Base):
    """An opaque bearer session token. Deleting the row is the logout."""

    __tablename__ = "auth_tokens"
    __table_args__ = (
        Index("auth_tokens_user_idx", "user_id"),
    )

    token: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=UTC_NOW, nullable=False
    )
    expires_at = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class TravelNote(Base):
    """A private notebook entry: where the traveller went and what they saw.
    Notes belong to their author alone and live until deleted."""

    __tablename__ = "travel_notes"
    __table_args__ = (
        Index("travel_notes_user_created_idx", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    place: Mapped[str] = mapped_column(Text, nullable=False)   # where they went
    body: Mapped[str] = mapped_column(Text, nullable=False)    # what they saw
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
