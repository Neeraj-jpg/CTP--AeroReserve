"""Typed domain objects for AeroReserve.

Flights are dated instances. An itinerary is one to three flight legs joined
by airport and minimum connection time. Each flight instance has its own cabin
seat inventory, so the same seat label on tomorrow's flight is independent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

MAX_PASSENGERS = 6
MAX_FLIGHT_LEGS = 3
MIN_CONNECTION_MINUTES = 45


class CabinClass(StrEnum):
    ECONOMY = "Economy"
    PREMIUM_ECONOMY = "Premium Economy"
    BUSINESS = "Business"
    FIRST = "First"

    @property
    def code(self) -> str:
        return {
            CabinClass.ECONOMY: "E",
            CabinClass.PREMIUM_ECONOMY: "P",
            CabinClass.BUSINESS: "B",
            CabinClass.FIRST: "F",
        }[self]

    @property
    def fare_rate_per_km(self) -> float:
        return {
            CabinClass.ECONOMY: 3.8,
            CabinClass.PREMIUM_ECONOMY: 5.5,
            CabinClass.BUSINESS: 9.5,
            CabinClass.FIRST: 15.0,
        }[self]


@dataclass(frozen=True, slots=True)
class Airport:
    code: str
    city: str
    name: str

    def __post_init__(self) -> None:
        if len(self.code) != 3 or not self.code.isalpha():
            raise ValueError("airport code must be a three-letter IATA-style code")


@dataclass(frozen=True, slots=True)
class Flight:
    """One scheduled, dated flight from one airport to another (all times IST)."""

    flight_id: str
    flight_number: str
    airline: str
    travel_date: date
    origin: Airport
    destination: Airport
    departure_at: datetime
    arrival_at: datetime
    distance_km: float
    aircraft: str = "A320"

    def __post_init__(self) -> None:
        if self.origin.code == self.destination.code:
            raise ValueError("flight origin and destination must differ")
        if self.arrival_at <= self.departure_at:
            raise ValueError("arrival must be after departure")
        if self.distance_km <= 0:
            raise ValueError("distance must be positive")

    @property
    def duration_minutes(self) -> int:
        return int((self.arrival_at - self.departure_at).total_seconds() // 60)


@dataclass(frozen=True, slots=True)
class Itinerary:
    flights: tuple[Flight, ...]

    def __post_init__(self) -> None:
        if not 1 <= len(self.flights) <= MAX_FLIGHT_LEGS:
            raise ValueError(f"an itinerary must have 1..{MAX_FLIGHT_LEGS} flight legs")
        for previous, following in zip(self.flights, self.flights[1:], strict=False):
            if previous.destination.code != following.origin.code:
                raise ValueError("connecting flights must use the same transfer airport")
            layover = (following.departure_at - previous.arrival_at).total_seconds() / 60
            if layover < MIN_CONNECTION_MINUTES:
                raise ValueError(
                    f"connection at {previous.destination.code} is shorter than "
                    f"{MIN_CONNECTION_MINUTES} minutes"
                )

    @property
    def origin(self) -> Airport:
        return self.flights[0].origin

    @property
    def destination(self) -> Airport:
        return self.flights[-1].destination

    @property
    def departure_at(self) -> datetime:
        return self.flights[0].departure_at

    @property
    def arrival_at(self) -> datetime:
        return self.flights[-1].arrival_at

    @property
    def connection_count(self) -> int:
        return len(self.flights) - 1

    @property
    def duration_minutes(self) -> int:
        return int((self.arrival_at - self.departure_at).total_seconds() // 60)

    @property
    def flight_ids(self) -> tuple[str, ...]:
        return tuple(f.flight_id for f in self.flights)


@dataclass(frozen=True, slots=True)
class Passenger:
    name: str
    age: int

    def __post_init__(self) -> None:
        if not self.name.strip() or len(self.name) > 60:
            raise ValueError("passenger name must contain 1..60 characters")
        if not 0 <= self.age <= 125:
            raise ValueError("passenger age must be between 0 and 125")


@dataclass(frozen=True, slots=True)
class Seat:
    label: str
    cabin: CabinClass
    row: int
    column: str
    window: bool
    aisle_after: bool = False


@dataclass(frozen=True, slots=True)
class BookingLeg:
    flight_id: str
    flight_number: str
    origin: str
    destination: str
    departure_at: datetime
    arrival_at: datetime
    seats: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Booking:
    pnr: str
    status: str
    travel_date: date
    cabin: CabinClass
    passengers: tuple[Passenger, ...]
    legs: tuple[BookingLeg, ...]
    fare: dict[str, object]
    created_at: datetime

    @property
    def origin(self) -> str:
        return self.legs[0].origin

    @property
    def destination(self) -> str:
        return self.legs[-1].destination


@dataclass(frozen=True, slots=True)
class FareQuote:
    cabin: CabinClass
    passenger_count: int
    lines: tuple[dict[str, object], ...]
    subtotal: float
    tax: float
    service_fee: float
    total: float

    def to_dict(self) -> dict[str, object]:
        return {
            "cabin": self.cabin.value,
            "passenger_count": self.passenger_count,
            "lines": list(self.lines),
            "subtotal": self.subtotal,
            "tax": self.tax,
            "service_fee": self.service_fee,
            "total": self.total,
            "currency": "INR",
        }
