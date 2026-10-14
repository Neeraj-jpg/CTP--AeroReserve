"""FastAPI transport layer for the AeroReserve demonstration platform."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any, cast

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from aerobooking.models import (
    MAX_FLIGHT_LEGS,
    MAX_PASSENGERS,
    Booking,
    CabinClass,
    Flight,
    Passenger,
)
from aerobooking.service import FlightBookingService, PlatformError

INDEX_PATH = Path(__file__).resolve().parent / "web" / "index.html"


class PassengerIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    age: int = Field(ge=0, le=125)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("passenger name cannot be blank")
        return value


class QuoteIn(BaseModel):
    flight_ids: list[str] = Field(min_length=1, max_length=MAX_FLIGHT_LEGS)
    travel_date: date
    cabin: CabinClass = CabinClass.ECONOMY
    passengers: list[PassengerIn] = Field(min_length=1, max_length=MAX_PASSENGERS)


class BookingIn(QuoteIn):
    strategy: str = "family-aware"


class HealthOut(BaseModel):
    status: str
    database: str
    active_bookings: int
    subscribers: int
    locks: dict[str, Any]


def _sse(kind: str, data: dict[str, Any]) -> str:
    return f"event: {kind}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def _flight_dict(flight: Flight) -> dict[str, object]:
    return {
        "flight_id": flight.flight_id,
        "flight_number": flight.flight_number,
        "airline": flight.airline,
        "origin": {"code": flight.origin.code, "city": flight.origin.city},
        "destination": {"code": flight.destination.code, "city": flight.destination.city},
        "departure_at": flight.departure_at.isoformat(timespec="minutes"),
        "arrival_at": flight.arrival_at.isoformat(timespec="minutes"),
        "duration_minutes": flight.duration_minutes,
        "distance_km": flight.distance_km,
        "aircraft": flight.aircraft,
    }


def _booking_dict(booking: Booking) -> dict[str, object]:
    return {
        "pnr": booking.pnr,
        "status": booking.status,
        "travel_date": booking.travel_date.isoformat(),
        "cabin": booking.cabin.value,
        "origin": booking.origin,
        "destination": booking.destination,
        "passengers": [{"name": p.name, "age": p.age} for p in booking.passengers],
        "legs": [
            {
                "flight_id": leg.flight_id,
                "flight_number": leg.flight_number,
                "origin": leg.origin,
                "destination": leg.destination,
                "departure_at": leg.departure_at.isoformat(timespec="minutes"),
                "arrival_at": leg.arrival_at.isoformat(timespec="minutes"),
                "seats": list(leg.seats),
            }
            for leg in booking.legs
        ],
        "fare": booking.fare,
        "created_at": booking.created_at.isoformat(timespec="seconds"),
    }


def _passengers(payload: QuoteIn) -> tuple[Passenger, ...]:
    return tuple(Passenger(name=item.name, age=item.age) for item in payload.passengers)


def create_app(service: FlightBookingService | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if app.state.service is None:
            app.state.service = FlightBookingService()
        yield

    app = FastAPI(
        title="AeroReserve Flight Booking Platform",
        version="1.0.0",
        description="Fictional dated-flight search, connections, cabin seats, booking and live updates.",
        lifespan=lifespan,
    )
    app.state.service = service

    def get_service(request: Request) -> FlightBookingService:
        return cast(FlightBookingService, request.app.state.service)

    @app.exception_handler(PlatformError)
    async def platform_error_handler(request: Request, exc: PlatformError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": str(exc)},
        )

    @app.get("/api/health", response_model=HealthOut, tags=["meta"])
    async def health(svc: FlightBookingService = Depends(get_service)) -> HealthOut:
        stats = await run_in_threadpool(svc.stats)
        return HealthOut(
            status="ok",
            database=cast(str, stats["database"]),
            active_bookings=cast(int, stats["active_bookings"]),
            subscribers=cast(int, stats["subscribers"]),
            locks=cast(dict[str, Any], stats["locks"]),
        )

    @app.get("/api/airports", tags=["search"])
    async def airports(svc: FlightBookingService = Depends(get_service)) -> list[dict[str, str]]:
        return await run_in_threadpool(svc.airports)

    @app.get("/api/flights/search", tags=["search"])
    async def search_flights(
        origin: str = Query(min_length=3, max_length=3),
        destination: str = Query(min_length=3, max_length=3),
        travel_date: date = Query(),
        cabin: CabinClass = Query(default=CabinClass.ECONOMY),
        max_connections: int = Query(default=2, ge=0, le=2),
        passengers: int = Query(default=1, ge=1, le=MAX_PASSENGERS),
        svc: FlightBookingService = Depends(get_service),
    ) -> dict[str, object]:
        itineraries = await run_in_threadpool(
            svc.search_itineraries, origin, destination, travel_date, cabin, max_connections
        )
        results: list[dict[str, object]] = []
        for itinerary in itineraries:
            quote = svc.quote(itinerary, cabin, passengers).to_dict()
            legs = []
            for flight in itinerary.flights:
                legs.append(
                    {
                        **_flight_dict(flight),
                        "cabin_seats_available": await run_in_threadpool(
                            svc.availability, flight.flight_id, cabin, travel_date
                        ),
                    }
                )
            results.append(
                {
                    "itinerary_id": "__".join(itinerary.flight_ids),
                    "travel_date": travel_date.isoformat(),
                    "origin": itinerary.origin.code,
                    "destination": itinerary.destination.code,
                    "departure_at": itinerary.departure_at.isoformat(timespec="minutes"),
                    "arrival_at": itinerary.arrival_at.isoformat(timespec="minutes"),
                    "duration_minutes": itinerary.duration_minutes,
                    "connection_count": itinerary.connection_count,
                    "legs": legs,
                    "quote": quote,
                }
            )
        return {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "travel_date": travel_date.isoformat(),
            "cabin": cabin.value,
            "minimum_connection_minutes": 45,
            "itineraries": results,
        }

    @app.get("/api/flights/{flight_id}/seats", tags=["availability"])
    async def flight_seats(
        flight_id: str,
        travel_date: date = Query(),
        cabin: CabinClass = Query(default=CabinClass.ECONOMY),
        svc: FlightBookingService = Depends(get_service),
    ) -> dict[str, object]:
        return await run_in_threadpool(svc.seat_map, flight_id, cabin, travel_date)

    @app.get("/api/flights/{flight_id}/events", tags=["live"])
    async def flight_events(
        flight_id: str,
        travel_date: date = Query(),
        cabin: CabinClass = Query(default=CabinClass.ECONOMY),
        svc: FlightBookingService = Depends(get_service),
    ) -> StreamingResponse:
        # Subscribe before taking the snapshot: a concurrent update can be
        # represented in the snapshot and/or queued as a delta, never missed.
        sub = svc.events.subscribe(flight_id)

        async def generate() -> AsyncIterator[str]:
            try:
                snapshot = await run_in_threadpool(svc.seat_map, flight_id, cabin, travel_date)
                yield _sse("snapshot", snapshot)
                async for event in svc.events.stream(sub):
                    if event.get("kind") == "heartbeat":
                        yield ": heartbeat\n\n"
                        continue
                    refreshed = await run_in_threadpool(svc.seat_map, flight_id, cabin, travel_date)
                    yield _sse(str(event.get("kind", "update")), {**event, "seat_map": refreshed})
            finally:
                svc.events.unsubscribe(sub.id)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/api/bookings/quote", tags=["bookings"])
    async def quote(
        payload: QuoteIn, svc: FlightBookingService = Depends(get_service)
    ) -> dict[str, object]:
        itinerary = await run_in_threadpool(
            svc.itinerary_from_ids, payload.flight_ids, payload.travel_date
        )
        return svc.quote(itinerary, payload.cabin, len(payload.passengers)).to_dict()

    @app.post("/api/bookings", status_code=201, tags=["bookings"])
    async def book(
        payload: BookingIn, svc: FlightBookingService = Depends(get_service)
    ) -> dict[str, object]:
        booking = await run_in_threadpool(
            svc.book,
            payload.flight_ids,
            payload.travel_date,
            payload.cabin,
            _passengers(payload),
            payload.strategy,
        )
        return _booking_dict(booking)

    @app.get("/api/bookings/{pnr}", tags=["bookings"])
    async def get_booking(
        pnr: str, svc: FlightBookingService = Depends(get_service)
    ) -> dict[str, object]:
        return _booking_dict(await run_in_threadpool(svc.booking, pnr))

    @app.post("/api/bookings/{pnr}/cancel", tags=["bookings"])
    async def cancel_booking(
        pnr: str, svc: FlightBookingService = Depends(get_service)
    ) -> dict[str, object]:
        return _booking_dict(await run_in_threadpool(svc.cancel, pnr))

    @app.get("/api/admin/audit", tags=["admin"])
    async def audit(
        limit: int = Query(default=20, ge=1, le=100),
        svc: FlightBookingService = Depends(get_service),
    ) -> list[dict[str, object]]:
        return await run_in_threadpool(svc.repository.audit_tail, limit)

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(INDEX_PATH)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
