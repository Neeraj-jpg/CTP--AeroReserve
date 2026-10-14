from __future__ import annotations

from datetime import date, timedelta

import pytest

from aerobooking.models import CabinClass
from aerobooking.schedule import india_today
from aerobooking.service import FlightBookingService, InvalidSearch


def test_search_finds_direct_and_connecting_itineraries(
    service: FlightBookingService, travel_date: date
) -> None:
    options = service.search_itineraries("VGA", "DEL", travel_date, CabinClass.ECONOMY, 2)
    assert options
    assert options[0].connection_count == 0
    assert any(option.connection_count == 1 for option in options)
    assert any(option.connection_count == 2 for option in options)


def test_every_connection_meets_45_minute_minimum(
    service: FlightBookingService, travel_date: date
) -> None:
    options = service.search_itineraries("VGA", "DEL", travel_date)
    for option in options:
        for first, second in zip(option.flights, option.flights[1:], strict=False):
            assert first.destination.code == second.origin.code
            assert (second.departure_at - first.arrival_at).total_seconds() >= 45 * 60


def test_connection_limit_is_respected(service: FlightBookingService, travel_date: date) -> None:
    direct_only = service.search_itineraries("VGA", "DEL", travel_date, max_connections=0)
    assert direct_only
    assert all(option.connection_count == 0 for option in direct_only)


def test_unknown_airport_is_rejected(service: FlightBookingService, travel_date: date) -> None:
    with pytest.raises(InvalidSearch, match="unknown airport"):
        service.search_itineraries("XXX", "DEL", travel_date)


def test_same_airport_is_rejected(service: FlightBookingService, travel_date: date) -> None:
    with pytest.raises(InvalidSearch, match="must differ"):
        service.search_itineraries("VGA", "VGA", travel_date)


def test_past_travel_date_is_rejected(service: FlightBookingService) -> None:
    with pytest.raises(InvalidSearch, match="within the next 180 days"):
        service.search_itineraries("VGA", "DEL", india_today() - timedelta(days=1))


def test_unknown_pair_returns_no_itinerary(
    service: FlightBookingService, travel_date: date
) -> None:
    assert service.search_itineraries("GOI", "DEL", travel_date, max_connections=0) == []
