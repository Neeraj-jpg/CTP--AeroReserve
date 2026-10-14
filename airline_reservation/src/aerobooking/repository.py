"""Booking repository and persistence mapping."""

from __future__ import annotations

import secrets
import string
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload, sessionmaker

from aerobooking.db import AuditRow, Base, BookingLegRow, BookingRow, get_engine
from aerobooking.models import Booking, BookingLeg, CabinClass, Passenger

_PNR_ALPHABET = string.ascii_uppercase.replace("O", "").replace("I", "") + string.digits


def new_pnr() -> str:
    return "".join(secrets.choice(_PNR_ALPHABET) for _ in range(10))


class BookingNotFound(LookupError):
    pass


class BookingStateError(ValueError):
    pass


class BookingRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self._engine = get_engine(database_url)
        self._sessions = sessionmaker(bind=self._engine, expire_on_commit=False, future=True)

    def initialize(self) -> None:
        Base.metadata.create_all(self._engine)

    def close(self) -> None:
        self._engine.dispose()

    def booked_seats(self, flight_id: str, cabin: CabinClass) -> set[str]:
        stmt = (
            select(BookingLegRow.seats_payload)
            .join(BookingRow, BookingRow.pnr == BookingLegRow.pnr)
            .where(
                BookingLegRow.flight_id == flight_id,
                BookingLegRow.cabin == cabin.value,
                BookingRow.status == "CONFIRMED",
            )
        )
        with self._sessions() as session:
            return {label for labels in session.scalars(stmt) for label in labels}

    def save(self, booking: Booking, distances: tuple[float, ...]) -> None:
        legs = [
            BookingLegRow(
                sequence=index,
                flight_id=leg.flight_id,
                flight_number=leg.flight_number,
                origin=leg.origin,
                destination=leg.destination,
                departure_at=leg.departure_at,
                arrival_at=leg.arrival_at,
                cabin=booking.cabin.value,
                seats_payload=list(leg.seats),
                distance_km=distances[index],
            )
            for index, leg in enumerate(booking.legs)
        ]
        row = BookingRow(
            pnr=booking.pnr,
            status=booking.status,
            travel_date=booking.travel_date.isoformat(),
            cabin=booking.cabin.value,
            origin=booking.origin,
            destination=booking.destination,
            passenger_payload=[{"name": p.name, "age": p.age} for p in booking.passengers],
            fare_payload=booking.fare,
            created_at=booking.created_at,
            legs=legs,
        )
        with self._sessions.begin() as session:
            session.add(row)
            session.add(
                AuditRow(
                    pnr=booking.pnr,
                    action="BOOK",
                    detail={
                        "flight_ids": [leg.flight_id for leg in booking.legs],
                        "seats": [list(leg.seats) for leg in booking.legs],
                    },
                    created_at=booking.created_at,
                )
            )

    def get(self, pnr: str) -> Booking:
        stmt = (
            select(BookingRow)
            .where(BookingRow.pnr == pnr.upper())
            .options(selectinload(BookingRow.legs))
        )
        with self._sessions() as session:
            row = session.scalars(stmt).first()
            if row is None:
                raise BookingNotFound(f"booking {pnr} was not found")
            return _to_domain(row)

    def cancel(self, pnr: str) -> Booking:
        with self._sessions.begin() as session:
            row = session.scalars(
                select(BookingRow)
                .where(BookingRow.pnr == pnr.upper())
                .options(selectinload(BookingRow.legs))
            ).first()
            if row is None:
                raise BookingNotFound(f"booking {pnr} was not found")
            if row.status != "CONFIRMED":
                raise BookingStateError(f"booking {pnr} is already {row.status.lower()}")
            now = datetime.now()
            row.status = "CANCELLED"
            row.cancelled_at = now
            session.add(
                AuditRow(
                    pnr=row.pnr,
                    action="CANCEL",
                    detail={"flight_ids": [leg.flight_id for leg in row.legs]},
                    created_at=now,
                )
            )
            session.flush()
            return _to_domain(row)

    def active_booking_count(self) -> int:
        from sqlalchemy import func

        with self._sessions() as session:
            return int(
                session.scalar(
                    select(func.count())
                    .select_from(BookingRow)
                    .where(BookingRow.status == "CONFIRMED")
                )
                or 0
            )

    def audit_tail(self, limit: int = 20) -> list[dict[str, object]]:
        stmt = select(AuditRow).order_by(AuditRow.id.desc()).limit(max(1, min(limit, 100)))
        with self._sessions() as session:
            rows = session.scalars(stmt).all()
            return [
                {
                    "id": row.id,
                    "pnr": row.pnr,
                    "action": row.action,
                    "detail": row.detail,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ]


def _to_domain(row: BookingRow) -> Booking:
    passengers = tuple(
        Passenger(name=item["name"], age=int(item["age"])) for item in row.passenger_payload
    )
    legs = tuple(
        BookingLeg(
            flight_id=leg.flight_id,
            flight_number=leg.flight_number,
            origin=leg.origin,
            destination=leg.destination,
            departure_at=leg.departure_at,
            arrival_at=leg.arrival_at,
            seats=tuple(leg.seats_payload),
        )
        for leg in row.legs
    )
    return Booking(
        pnr=row.pnr,
        status=row.status,
        travel_date=date.fromisoformat(row.travel_date),
        cabin=CabinClass(row.cabin),
        passengers=passengers,
        legs=legs,
        fare=dict(row.fare_payload),
        created_at=row.created_at,
    )
