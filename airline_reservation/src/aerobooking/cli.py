"""Command-line entry point for route search and booking demos."""

from __future__ import annotations

import argparse
import json
import threading
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from aerobooking.models import CabinClass, Passenger
from aerobooking.schedule import india_today
from aerobooking.service import FlightBookingService, PlatformError


def _default_date() -> str:
    return (india_today() + timedelta(days=1)).isoformat()


def _positive_int(value: str) -> int:
    try:
        count = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if not 1 <= count <= 500:
        raise argparse.ArgumentTypeError("must be between 1 and 500")
    return count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aerobooking", description="AeroReserve sample flight booking"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("airports", help="list sample airports")

    search = sub.add_parser("search", help="search direct and connecting flights")
    search.add_argument("--from", dest="origin", required=True)
    search.add_argument("--to", dest="destination", required=True)
    search.add_argument("--date", default=_default_date())
    search.add_argument(
        "--cabin", choices=[c.value for c in CabinClass], default=CabinClass.ECONOMY.value
    )
    search.add_argument("--connections", type=int, choices=range(0, 3), default=2)

    book = sub.add_parser("book", help="book the first matching itinerary")
    book.add_argument("--from", dest="origin", required=True)
    book.add_argument("--to", dest="destination", required=True)
    book.add_argument("--date", default=_default_date())
    book.add_argument(
        "--cabin", choices=[c.value for c in CabinClass], default=CabinClass.ECONOMY.value
    )
    book.add_argument(
        "--strategy", choices=["family-aware", "first-fit", "window-first"], default="family-aware"
    )
    book.add_argument(
        "-p", "--passenger", action="append", default=[], help="NAME:AGE; repeat for each traveller"
    )

    retrieve = sub.add_parser("booking", help="show booking by PNR")
    retrieve.add_argument("pnr")
    cancel = sub.add_parser("cancel", help="cancel a confirmed itinerary")
    cancel.add_argument("pnr")

    stress = sub.add_parser("stress", help="race requests for one flight's cabin seats")
    stress.add_argument("--flight", default="AS110")
    stress.add_argument("--date", default=_default_date())
    stress.add_argument(
        "--cabin", choices=[c.value for c in CabinClass], default=CabinClass.ECONOMY.value
    )
    stress.add_argument("--threads", type=_positive_int, default=50)
    return parser


def _parse_passengers(values: list[str]) -> tuple[Passenger, ...]:
    if not values:
        return (Passenger("Demo Passenger", 30),)
    result = []
    for item in values:
        try:
            name, age = item.rsplit(":", 1)
            result.append(Passenger(name, int(age)))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"invalid passenger {item!r}; expected NAME:AGE") from exc
    return tuple(result)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = FlightBookingService()
    try:
        if args.command == "airports":
            print(json.dumps(service.airports(), indent=2))
            return 0
        if args.command == "search":
            itineraries = service.search_itineraries(
                args.origin,
                args.destination,
                date.fromisoformat(args.date),
                CabinClass(args.cabin),
                args.connections,
            )
            data = []
            for it in itineraries:
                data.append(
                    {
                        "flights": [f.flight_number for f in it.flights],
                        "route": [it.origin.code, *[f.destination.code for f in it.flights]],
                        "depart": it.departure_at.isoformat(timespec="minutes"),
                        "arrive": it.arrival_at.isoformat(timespec="minutes"),
                        "connections": it.connection_count,
                        "fare_per_passenger": service.quote(it, CabinClass(args.cabin), 1).total,
                    }
                )
            print(json.dumps(data, indent=2))
            return 0
        if args.command == "book":
            travel_date = date.fromisoformat(args.date)
            cabin = CabinClass(args.cabin)
            itineraries = service.search_itineraries(
                args.origin, args.destination, travel_date, cabin, 2
            )
            if not itineraries:
                raise ValueError("no itinerary found")
            booking = service.book(
                itineraries[0].flight_ids,
                travel_date,
                cabin,
                _parse_passengers(args.passenger),
                args.strategy,
            )
            print(
                json.dumps(
                    {
                        "pnr": booking.pnr,
                        "legs": [leg.flight_number for leg in booking.legs],
                        "seats": [list(leg.seats) for leg in booking.legs],
                        "fare": booking.fare,
                    },
                    indent=2,
                )
            )
            return 0
        if args.command == "booking":
            booking = service.booking(args.pnr)
            print(
                json.dumps(
                    {
                        "pnr": booking.pnr,
                        "status": booking.status,
                        "origin": booking.origin,
                        "destination": booking.destination,
                        "legs": [leg.flight_number for leg in booking.legs],
                        "fare": booking.fare,
                    },
                    indent=2,
                )
            )
            return 0
        if args.command == "cancel":
            booking = service.cancel(args.pnr)
            print(f"CANCELLED {booking.pnr}; seats released on {len(booking.legs)} flight leg(s)")
            return 0
        if args.command == "stress":
            flight = next(
                f
                for f in service.flights(date.fromisoformat(args.date))
                if f.flight_number == args.flight
            )
            barrier = threading.Barrier(args.threads)

            def worker(i: int) -> tuple[str, ...] | None:
                barrier.wait()
                try:
                    booking = service.book(
                        [flight.flight_id],
                        flight.travel_date,
                        CabinClass(args.cabin),
                        [Passenger(f"Stress{i}", 30)],
                    )
                    return booking.legs[0].seats
                except PlatformError:
                    return None

            with ThreadPoolExecutor(max_workers=args.threads) as pool:
                results = list(pool.map(worker, range(args.threads)))
            successes = [assignment for assignment in results if assignment is not None]
            failures = args.threads - len(successes)
            flat = [seat for assignment in successes for seat in assignment]
            duplicates = len(flat) - len(set(flat))
            print(
                f"attempts: {args.threads}; confirmed: {len(successes)}; rejected: {failures}; duplicate seat assignments: {duplicates}"
            )
            return 0 if duplicates == 0 else 1
    except (PlatformError, ValueError, StopIteration) as exc:
        print(f"error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
