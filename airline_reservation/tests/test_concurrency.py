from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from aerobooking.models import CabinClass, Passenger
from aerobooking.service import FlightBookingService, PlatformError


def test_threads_racing_for_one_flight_do_not_receive_duplicate_seats(
    service: FlightBookingService, travel_date: date
) -> None:
    flight = next(f for f in service.flights(travel_date) if f.flight_number == "AS110")
    contenders = 50
    gate = threading.Barrier(contenders)
    successes: list[tuple[str, ...]] = []
    errors: list[Exception] = []
    result_lock = threading.Lock()

    def worker(index: int) -> None:
        gate.wait()
        try:
            booking = service.book(
                [flight.flight_id],
                travel_date,
                CabinClass.ECONOMY,
                [Passenger(f"Guest {index}", 30)],
            )
            with result_lock:
                successes.append(booking.legs[0].seats)
        except PlatformError as exc:
            with result_lock:
                errors.append(exc)

    with ThreadPoolExecutor(max_workers=contenders) as pool:
        futures = [pool.submit(worker, i) for i in range(contenders)]
        for future in as_completed(futures):
            future.result()

    sold = [seat for assignment in successes for seat in assignment]
    assert len(successes) == 36
    assert len(errors) == contenders - 36
    assert len(sold) == len(set(sold)) == 36
    # Check persisted active assignments, not just thread return values.
    assert service.repository.booked_seats(flight.flight_id, CabinClass.ECONOMY) == set(sold)
