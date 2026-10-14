"""SQLAlchemy persistence setup. SQLite is the zero-configuration demo default."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

DEFAULT_SQLITE_URL = "sqlite+pysqlite:///./aerobooking.db"


class Base(DeclarativeBase):
    pass


class BookingRow(Base):
    __tablename__ = "bookings"

    pnr: Mapped[str] = mapped_column(String(10), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    travel_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    cabin: Mapped[str] = mapped_column(String(32), nullable=False)
    origin: Mapped[str] = mapped_column(String(3), nullable=False)
    destination: Mapped[str] = mapped_column(String(3), nullable=False)
    passenger_payload: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    fare_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[Any] = mapped_column(DateTime, nullable=False)
    cancelled_at: Mapped[Any | None] = mapped_column(DateTime, nullable=True)
    legs: Mapped[list[BookingLegRow]] = relationship(
        back_populates="booking", cascade="all, delete-orphan", order_by="BookingLegRow.sequence"
    )


class BookingLegRow(Base):
    __tablename__ = "booking_legs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pnr: Mapped[str] = mapped_column(ForeignKey("bookings.pnr", ondelete="CASCADE"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    flight_id: Mapped[str] = mapped_column(String(32), nullable=False)
    flight_number: Mapped[str] = mapped_column(String(8), nullable=False)
    origin: Mapped[str] = mapped_column(String(3), nullable=False)
    destination: Mapped[str] = mapped_column(String(3), nullable=False)
    departure_at: Mapped[Any] = mapped_column(DateTime, nullable=False)
    arrival_at: Mapped[Any] = mapped_column(DateTime, nullable=False)
    cabin: Mapped[str] = mapped_column(String(32), nullable=False)
    seats_payload: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    distance_km: Mapped[float] = mapped_column(nullable=False)

    booking: Mapped[BookingRow] = relationship(back_populates="legs")


Index("ix_leg_flight_cabin", BookingLegRow.flight_id, BookingLegRow.cabin)


class AuditRow(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pnr: Mapped[str] = mapped_column(String(10), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[Any] = mapped_column(DateTime, nullable=False)


def _normalize_database_url(value: str) -> str:
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


def database_url() -> str:
    """Prefer DATABASE_URL; otherwise use the self-seeding local SQLite file."""
    explicit = os.getenv("DATABASE_URL", "").strip()
    if explicit:
        return _normalize_database_url(explicit)
    custom_path = os.getenv("AEROBOOKING_SQLITE_PATH", "").strip()
    if not custom_path:
        return DEFAULT_SQLITE_URL
    if "://" in custom_path:
        return _normalize_database_url(custom_path)
    return f"sqlite+pysqlite:///{custom_path}"


_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def get_engine(url: str | None = None) -> Engine:
    global _engine
    selected = url or database_url()
    if url is not None:
        kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True}
        if selected.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 20}
            if selected.endswith(":memory:"):
                kwargs["poolclass"] = StaticPool
        return create_engine(selected, **kwargs)
    if _engine is None:
        kwargs = {"future": True, "pool_pre_ping": True}
        if selected.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 20}
            if selected.endswith(":memory:"):
                kwargs["poolclass"] = StaticPool
            elif selected.startswith("sqlite+pysqlite:///./"):
                Path(".").mkdir(parents=True, exist_ok=True)
        _engine = create_engine(selected, **kwargs)
    return _engine


def get_session_factory(url: str | None = None) -> sessionmaker[Session]:
    global _SessionFactory
    if url is not None:
        return sessionmaker(bind=get_engine(url), expire_on_commit=False, future=True)
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionFactory


def reset_database_for_tests() -> None:
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None
