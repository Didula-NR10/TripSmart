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

    __tablename__ = "weather_observations"
    __table_args__ = (
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

    __tablename__ = "ground_reports"
    __table_args__ = (
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
    location: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    author: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    posted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=UTC_NOW, nullable=False
    )

class User(Base):

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    country: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    avatar_url: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    google_sub: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=UTC_NOW, nullable=False
    )
    updated_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=UTC_NOW, nullable=False
    )
    last_login_at = mapped_column(TIMESTAMP(timezone=True), nullable=True)

class EmailOtp(Base):

    __tablename__ = "email_otps"
    __table_args__ = (
        Index("email_otps_email_purpose_idx", "email", "purpose"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    expires_at = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=UTC_NOW, nullable=False
    )

class AuthToken(Base):

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

class TravelJournal(Base):

    __tablename__ = "travel_journals"
    __table_args__ = (
        Index("travel_journals_user_created_idx", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    created_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=UTC_NOW, nullable=False
    )

class TravelNote(Base):

    __tablename__ = "travel_notes"
    __table_args__ = (
        Index("travel_notes_user_created_idx", "user_id", "created_at"),
        Index("travel_notes_journal_page_idx", "journal_id", "page_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    place: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    photo_url: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    journal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("travel_journals.id", ondelete="CASCADE"),
        nullable=True,
    )
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=UTC_NOW, nullable=False
    )

class ForecastRun(Base):

    __tablename__ = "forecast_runs"
    __table_args__ = (
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

class PushSubscription(Base):

    __tablename__ = "push_subscriptions"
    __table_args__ = (
        Index("push_subscriptions_district_idx", "district_id"),
    )

    expo_token: Mapped[str] = mapped_column(Text, primary_key=True)
    district_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("districts.id", ondelete="CASCADE"),
        nullable=False,
    )
    updated_at = mapped_column(
        TIMESTAMP(timezone=True), server_default=UTC_NOW, nullable=False
    )
