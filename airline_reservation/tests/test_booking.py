from __future__ import annotations

from datetime import date, timedelta

import pytest

from aerobooking.models import CabinClass, Passenger
from aerobooking.service import FlightBookingService, InvalidBooking


def _flight_ids(service: FlightBookingService, travel_date: date, *numbers: str) -> list[str]:
    by_number = {flight.flight_number: flight.flight_id for flight in service.flights(travel_date)}
    return [by_number[number] for number in numbers]


def test_direct_booking_returns_pnr_and_seats(
    service: FlightBookingService, travel_date: date
) -> None:
    booking = service.book(
        _flight_ids(service, travel_date, "AS110"),
        travel_date,
        CabinClass.ECONOMY,
        [Passenger("Asha Rao", 22), Passenger("Ravi Rao", 25)],
    )
    assert len(booking.pnr) == 10
    assert booking.status == "CONFIRMED"
    assert len(booking.legs) == 1
    assert len(booking.legs[0].seats) == 2
    assert booking.fare["total"] > 0


def test_one_pnr_covers_each_connecting_flight(
    service: FlightBookingService, travel_date: date
) -> None:
    ids = _flight_ids(service, travel_date, "AS101", "AS205")
    booking = service.book(ids, travel_date, CabinClass.ECONOMY, [Passenger("Kiran", 31)])
    assert [leg.flight_number for leg in booking.legs] == ["AS101", "AS205"]
    assert booking.legs[0].destination == booking.legs[1].origin == "HYD"
    assert len({leg.seats[0] for leg in booking.legs}) == 1
    assert service.availability(ids[0], CabinClass.ECONOMY, travel_date) == 35
    assert service.availability(ids[1], CabinClass.ECONOMY, travel_date) == 35


def test_same_flight_on_another_date_has_separate_inventory(
    service: FlightBookingService, travel_date: date
) -> None:
    later = travel_date + timedelta(days=1)
    today_flight = _flight_ids(service, travel_date, "AS110")[0]
    later_flight = _flight_ids(service, later, "AS110")[0]
    service.book([today_flight], travel_date, CabinClass.BUSINESS, [Passenger("Date One", 28)])
    assert service.availability(today_flight, CabinClass.BUSINESS, travel_date) == 7
    assert service.availability(later_flight, CabinClass.BUSINESS, later) == 8


def test_booking_one_cabin_does_not_consume_another(
    service: FlightBookingService, travel_date: date
) -> None:
    flight_id = _flight_ids(service, travel_date, "AS110")[0]
    service.book([flight_id], travel_date, CabinClass.ECONOMY, [Passenger("Eco", 40)])
    assert service.availability(flight_id, CabinClass.ECONOMY, travel_date) == 35
    assert service.availability(flight_id, CabinClass.FIRST, travel_date) == 4


def test_cancellation_releases_every_leg(service: FlightBookingService, travel_date: date) -> None:
    ids = _flight_ids(service, travel_date, "AS101", "AS205")
    booking = service.book(ids, travel_date, CabinClass.PREMIUM_ECONOMY, [Passenger("Guest", 40)])
    assert service.availability(ids[0], CabinClass.PREMIUM_ECONOMY, travel_date) == 11
    cancelled = service.cancel(booking.pnr)
    assert cancelled.status == "CANCELLED"
    assert service.availability(ids[0], CabinClass.PREMIUM_ECONOMY, travel_date) == 12
    assert service.availability(ids[1], CabinClass.PREMIUM_ECONOMY, travel_date) == 12


def test_cancel_twice_is_rejected(service: FlightBookingService, travel_date: date) -> None:
    flight_id = _flight_ids(service, travel_date, "AS110")[0]
    booking = service.book([flight_id], travel_date, CabinClass.ECONOMY, [Passenger("Guest", 40)])
    service.cancel(booking.pnr)
    with pytest.raises(InvalidBooking, match="already cancelled"):
        service.cancel(booking.pnr)


def test_invalid_connection_cannot_be_booked(
    service: FlightBookingService, travel_date: date
) -> None:
    ids = _flight_ids(service, travel_date, "AS101", "AS306")
    with pytest.raises(InvalidBooking, match="same transfer airport"):
        service.book(ids, travel_date, CabinClass.ECONOMY, [Passenger("Guest", 40)])


def test_party_over_six_is_rejected(service: FlightBookingService, travel_date: date) -> None:
    flight_id = _flight_ids(service, travel_date, "AS110")[0]
    passengers = [Passenger(f"P{i}", 30) for i in range(7)]
    with pytest.raises(InvalidBooking, match="between 1 and 6"):
        service.book([flight_id], travel_date, CabinClass.ECONOMY, passengers)


def test_quote_has_separate_tax_and_service_fee(
    service: FlightBookingService, travel_date: date
) -> None:
    itinerary = service.search_itineraries("VGA", "DEL", travel_date, max_connections=0)[0]
    quote = service.quote(itinerary, CabinClass.ECONOMY, 2).to_dict()
    assert quote["tax"] > 0
    assert quote["service_fee"] == 198.0
    assert quote["total"] == round(quote["subtotal"] + quote["tax"] + quote["service_fee"], 2)
