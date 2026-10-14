"""Flight search, fare, booking, cancellation and live-event application service."""

from __future__ import annotations

import asyncio
import threading
from collections import defaultdict
from collections.abc import AsyncIterator, Iterable, Iterator, Sequence
from contextlib import ExitStack, contextmanager, suppress
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from queue import Empty, Full, Queue
from typing import Any

from aerobooking.availability import STRATEGIES, allocate_seats, cabin_capacity, seat_map
from aerobooking.models import (
    MAX_FLIGHT_LEGS,
    MAX_PASSENGERS,
    MIN_CONNECTION_MINUTES,
    Booking,
    BookingLeg,
    CabinClass,
    FareQuote,
    Flight,
    Itinerary,
    Passenger,
)
from aerobooking.repository import (
    BookingNotFound,
    BookingRepository,
    BookingStateError,
    new_pnr,
)
from aerobooking.schedule import AIRPORT_BY_CODE, AIRPORTS, flights_for_date, india_today


class PlatformError(Exception):
    code = "platform_error"
    status_code = 400


class InvalidSearch(PlatformError):
    code = "invalid_search"
    status_code = 422


class InvalidBooking(PlatformError):
    code = "invalid_booking"
    status_code = 422


class NoItinerary(PlatformError):
    code = "no_itinerary"
    status_code = 404


class CapacityError(PlatformError):
    code = "capacity_exceeded"
    status_code = 409


class BusyError(PlatformError):
    code = "busy_try_again"
    status_code = 503


@dataclass(slots=True)
class _Subscriber:
    id: int
    flight_id: str
    queue: Queue[dict[str, Any]]


class EventBus:
    """Thread-safe, bounded in-process publisher for per-flight SSE streams."""

    def __init__(self, queue_size: int = 128) -> None:
        self._queue_size = queue_size
        self._guard = threading.Lock()
        self._ids = 0
        self._subscribers: dict[int, _Subscriber] = {}

    def subscribe(self, flight_id: str) -> _Subscriber:
        with self._guard:
            self._ids += 1
            sub = _Subscriber(self._ids, flight_id, Queue(maxsize=self._queue_size))
            self._subscribers[sub.id] = sub
            return sub

    def unsubscribe(self, sub_id: int) -> None:
        with self._guard:
            self._subscribers.pop(sub_id, None)

    @property
    def subscriber_count(self) -> int:
        with self._guard:
            return len(self._subscribers)

    def publish(self, flight_id: str, event: dict[str, Any]) -> None:
        with self._guard:
            targets = [sub for sub in self._subscribers.values() if sub.flight_id == flight_id]
            for sub in targets:
                try:
                    sub.queue.put_nowait(event)
                except Full:
                    with suppress(Empty):
                        sub.queue.get_nowait()
                    with suppress(Full):
                        sub.queue.put_nowait(event)

    async def stream(
        self, sub: _Subscriber, heartbeat_seconds: float = 12.0
    ) -> AsyncIterator[dict[str, Any]]:
        try:
            while True:
                try:
                    item = await asyncio.to_thread(sub.queue.get, True, heartbeat_seconds)
                    yield item
                except Empty:
                    yield {"kind": "heartbeat", "flight_id": sub.flight_id}
        finally:
            self.unsubscribe(sub.id)


class FlightLockManager:
    """Per-flight locks; acquire multi-leg itineraries in sorted order."""

    def __init__(self, timeout: float = 5.0) -> None:
        self._guard = threading.Lock()
        self._locks: defaultdict[str, threading.RLock] = defaultdict(threading.RLock)
        self._timeout = timeout
        self._acquisitions = 0
        self._contentions = 0

    @contextmanager
    def acquire_many(self, flight_ids: Iterable[str]) -> Iterator[None]:
        with self._guard:
            locks = [(key, self._locks[key]) for key in sorted(set(flight_ids))]
        with ExitStack() as stack:
            for key, lock in locks:
                if not lock.acquire(blocking=False):
                    with self._guard:
                        self._contentions += 1
                    if not lock.acquire(timeout=self._timeout):
                        raise BusyError(f"flight {key} is busy; please retry")
                with self._guard:
                    self._acquisitions += 1
                stack.callback(lock.release)
            yield

    def stats(self) -> dict[str, int | float]:
        with self._guard:
            return {
                "tracked_flights": len(self._locks),
                "acquisitions": self._acquisitions,
                "contentions": self._contentions,
                "contention_rate": round(self._contentions / self._acquisitions, 4)
                if self._acquisitions
                else 0.0,
            }


class FlightBookingService:
    def __init__(self, repository: BookingRepository | None = None) -> None:
        self.repository = repository or BookingRepository()
        self.repository.initialize()
        self.events = EventBus()
        self.locks = FlightLockManager()

    @staticmethod
    def airports() -> list[dict[str, str]]:
        return [{"code": a.code, "city": a.city, "name": a.name} for a in AIRPORTS]

    @staticmethod
    def _check_date(travel_date: date) -> None:
        today = india_today()
        if travel_date < today or travel_date > today + timedelta(days=180):
            raise InvalidSearch("travel date must be today or within the next 180 days")

    @staticmethod
    def _check_airport(code: str) -> str:
        normalized = code.strip().upper()
        if normalized not in AIRPORT_BY_CODE:
            raise InvalidSearch(f"unknown airport code: {code}")
        return normalized

    def flights(self, travel_date: date) -> tuple[Flight, ...]:
        self._check_date(travel_date)
        return flights_for_date(travel_date)

    def search_itineraries(
        self,
        origin: str,
        destination: str,
        travel_date: date,
        cabin: CabinClass = CabinClass.ECONOMY,
        max_connections: int = 2,
    ) -> list[Itinerary]:
        origin = self._check_airport(origin)
        destination = self._check_airport(destination)
        self._check_date(travel_date)
        if origin == destination:
            raise InvalidSearch("origin and destination airports must differ")
        if not 0 <= max_connections <= 2:
            raise InvalidSearch("max_connections must be between 0 and 2")

        all_flights = self.flights(travel_date)
        outgoing: dict[str, list[Flight]] = defaultdict(list)
        for flight in all_flights:
            outgoing[flight.origin.code].append(flight)
        for flights in outgoing.values():
            flights.sort(key=lambda flight: (flight.departure_at, flight.flight_number))

        found: list[Itinerary] = []
        max_legs = max_connections + 1

        def walk(airport_code: str, path: tuple[Flight, ...], visited: frozenset[str]) -> None:
            if path and airport_code == destination:
                found.append(Itinerary(path))
                return
            if len(path) >= max_legs:
                return
            earliest = (
                path[-1].arrival_at + timedelta(minutes=MIN_CONNECTION_MINUTES) if path else None
            )
            for flight in outgoing.get(airport_code, []):
                if earliest is not None and flight.departure_at < earliest:
                    continue
                next_airport = flight.destination.code
                if next_airport in visited:
                    continue
                walk(next_airport, (*path, flight), visited | {next_airport})

        walk(origin, (), frozenset({origin}))
        found.sort(
            key=lambda itinerary: (
                itinerary.arrival_at,
                itinerary.connection_count,
                sum(f.distance_km for f in itinerary.flights),
                itinerary.flight_ids,
            )
        )
        return found

    def itinerary_from_ids(self, flight_ids: Sequence[str], travel_date: date) -> Itinerary:
        self._check_date(travel_date)
        if not 1 <= len(flight_ids) <= MAX_FLIGHT_LEGS:
            raise InvalidBooking(f"choose between 1 and {MAX_FLIGHT_LEGS} flight legs")
        available = {flight.flight_id: flight for flight in self.flights(travel_date)}
        if len(set(flight_ids)) != len(flight_ids):
            raise InvalidBooking("an itinerary cannot repeat a flight")
        try:
            flights = tuple(available[flight_id] for flight_id in flight_ids)
        except KeyError as exc:
            raise InvalidBooking("selected flight is not scheduled on that travel date") from exc
        try:
            return Itinerary(flights)
        except ValueError as exc:
            raise InvalidBooking(str(exc)) from exc

    def availability(self, flight_id: str, cabin: CabinClass, travel_date: date) -> int:
        flight = self._flight_by_id(flight_id, travel_date)
        del flight
        return cabin_capacity(cabin) - len(self.repository.booked_seats(flight_id, cabin))

    def seat_map(self, flight_id: str, cabin: CabinClass, travel_date: date) -> dict[str, object]:
        flight = self._flight_by_id(flight_id, travel_date)
        occupied = self.repository.booked_seats(flight_id, cabin)
        seats = seat_map(cabin, occupied)
        return {
            "flight_id": flight.flight_id,
            "flight_number": flight.flight_number,
            "travel_date": travel_date.isoformat(),
            "origin": flight.origin.code,
            "destination": flight.destination.code,
            "cabin": cabin.value,
            "capacity": cabin_capacity(cabin),
            "available": len(seats) - len(occupied),
            "seats": seats,
        }

    def _flight_by_id(self, flight_id: str, travel_date: date) -> Flight:
        for flight in self.flights(travel_date):
            if flight.flight_id == flight_id:
                return flight
        raise InvalidSearch("flight does not exist for the selected travel date")

    @staticmethod
    def quote(itinerary: Itinerary, cabin: CabinClass, passenger_count: int) -> FareQuote:
        if not 1 <= passenger_count <= MAX_PASSENGERS:
            raise InvalidBooking(f"passenger count must be between 1 and {MAX_PASSENGERS}")
        lines: list[dict[str, object]] = []
        subtotal = 0.0
        for flight in itinerary.flights:
            amount = round(flight.distance_km * cabin.fare_rate_per_km * passenger_count, 2)
            subtotal += amount
            lines.append(
                {
                    "flight_number": flight.flight_number,
                    "route": f"{flight.origin.code}-{flight.destination.code}",
                    "distance_km": flight.distance_km,
                    "rate_per_km": cabin.fare_rate_per_km,
                    "passengers": passenger_count,
                    "amount": amount,
                }
            )
        subtotal = round(subtotal, 2)
        tax = round(subtotal * 0.05, 2)
        service_fee = round(99.0 * passenger_count, 2)
        total = round(subtotal + tax + service_fee, 2)
        return FareQuote(
            cabin=cabin,
            passenger_count=passenger_count,
            lines=tuple(lines),
            subtotal=subtotal,
            tax=tax,
            service_fee=service_fee,
            total=total,
        )

    def book(
        self,
        flight_ids: Sequence[str],
        travel_date: date,
        cabin: CabinClass,
        passengers: Sequence[Passenger],
        strategy: str = "family-aware",
    ) -> Booking:
        if not 1 <= len(passengers) <= MAX_PASSENGERS:
            raise InvalidBooking(f"passenger count must be between 1 and {MAX_PASSENGERS}")
        if strategy not in STRATEGIES:
            raise InvalidBooking(f"strategy must be one of: {', '.join(STRATEGIES)}")
        itinerary = self.itinerary_from_ids(flight_ids, travel_date)
        passenger_tuple = tuple(passengers)
        with self.locks.acquire_many(itinerary.flight_ids):
            legs: list[BookingLeg] = []
            for flight in itinerary.flights:
                occupied = self.repository.booked_seats(flight.flight_id, cabin)
                try:
                    labels = allocate_seats(cabin, len(passenger_tuple), occupied, strategy)
                except ValueError as exc:
                    raise CapacityError(str(exc)) from exc
                # Recheck while every flight lock in the itinerary is held.
                latest = self.repository.booked_seats(flight.flight_id, cabin)
                if set(labels) & latest:
                    raise CapacityError(
                        f"a {cabin.value} seat was just taken on {flight.flight_number}"
                    )
                legs.append(
                    BookingLeg(
                        flight_id=flight.flight_id,
                        flight_number=flight.flight_number,
                        origin=flight.origin.code,
                        destination=flight.destination.code,
                        departure_at=flight.departure_at,
                        arrival_at=flight.arrival_at,
                        seats=labels,
                    )
                )
            fare = self.quote(itinerary, cabin, len(passenger_tuple)).to_dict()
            booking = Booking(
                pnr=new_pnr(),
                status="CONFIRMED",
                travel_date=travel_date,
                cabin=cabin,
                passengers=passenger_tuple,
                legs=tuple(legs),
                fare=fare,
                created_at=datetime.now().replace(microsecond=0),
            )
            self.repository.save(booking, tuple(f.distance_km for f in itinerary.flights))
        for leg in booking.legs:
            self.events.publish(
                leg.flight_id,
                {
                    "kind": "booking",
                    "pnr": booking.pnr,
                    "flight_id": leg.flight_id,
                    "seats": list(leg.seats),
                },
            )
        return booking

    def booking(self, pnr: str) -> Booking:
        try:
            return self.repository.get(pnr)
        except BookingNotFound as exc:
            raise NoItinerary(str(exc)) from exc

    def cancel(self, pnr: str) -> Booking:
        existing = self.booking(pnr)
        flight_ids = tuple(leg.flight_id for leg in existing.legs)
        with self.locks.acquire_many(flight_ids):
            try:
                cancelled = self.repository.cancel(pnr)
            except BookingNotFound as exc:
                raise NoItinerary(str(exc)) from exc
            except BookingStateError as exc:
                raise InvalidBooking(str(exc)) from exc
        for leg in cancelled.legs:
            self.events.publish(
                leg.flight_id,
                {
                    "kind": "cancellation",
                    "pnr": cancelled.pnr,
                    "flight_id": leg.flight_id,
                    "seats": list(leg.seats),
                },
            )
        return cancelled

    def stats(self) -> dict[str, object]:
        return {
            "database": "sqlite" if "sqlite" in str(self.repository._engine.url) else "postgresql",
            "active_bookings": self.repository.active_booking_count(),
            "subscribers": self.events.subscriber_count,
            "locks": self.locks.stats(),
        }
