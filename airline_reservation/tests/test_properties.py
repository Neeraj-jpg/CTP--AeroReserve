from __future__ import annotations

from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from aerobooking.availability import allocate_seats, cabin_seats
from aerobooking.models import CabinClass
from aerobooking.service import FlightBookingService

_ECONOMY_LABELS = [seat.label for seat in cabin_seats(CabinClass.ECONOMY)]


@given(
    count=st.integers(min_value=1, max_value=6),
    occupied=st.sets(st.sampled_from(_ECONOMY_LABELS), max_size=20),
)
def test_seat_selector_never_returns_occupied_or_duplicate_labels(
    count: int, occupied: set[str]
) -> None:
    free_count = len(_ECONOMY_LABELS) - len(occupied)
    if free_count < count:
        return
    result = allocate_seats(CabinClass.ECONOMY, count, occupied, "first-fit")
    assert len(result) == count
    assert len(set(result)) == count
    assert not (set(result) & occupied)


def test_fare_is_monotonic_in_passenger_count(
    service: FlightBookingService, travel_date: date
) -> None:
    itinerary = service.search_itineraries("VGA", "DEL", travel_date, max_connections=0)[0]
    fares = [service.quote(itinerary, CabinClass.BUSINESS, n).total for n in range(1, 7)]
    assert fares == sorted(fares)


@given(count=st.integers(min_value=1, max_value=6))
def test_family_allocator_returns_requested_number_of_seats(count: int) -> None:
    seats = allocate_seats(CabinClass.ECONOMY, count, (), "family-aware")
    assert len(seats) == count
