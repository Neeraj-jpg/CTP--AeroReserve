from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from aerobooking.api import create_app
from aerobooking.models import CabinClass
from aerobooking.service import FlightBookingService


def test_airport_list_and_search_response(service: FlightBookingService, travel_date: date) -> None:
    client = TestClient(create_app(service))
    airports = client.get("/api/airports")
    assert airports.status_code == 200
    assert {item["code"] for item in airports.json()} >= {"VGA", "HYD", "DEL"}
    search = client.get(
        "/api/flights/search",
        params={
            "origin": "VGA",
            "destination": "DEL",
            "travel_date": travel_date.isoformat(),
            "cabin": "Economy",
        },
    )
    assert search.status_code == 200
    result = search.json()
    assert result["minimum_connection_minutes"] == 45
    assert result["itineraries"]
    assert result["itineraries"][0]["connection_count"] == 0


def test_quote_book_and_cancel_api(service: FlightBookingService, travel_date: date) -> None:
    client = TestClient(create_app(service))
    direct = service.search_itineraries("VGA", "DEL", travel_date, CabinClass.ECONOMY, 0)[0]
    payload = {
        "flight_ids": list(direct.flight_ids),
        "travel_date": travel_date.isoformat(),
        "cabin": "Economy",
        "passengers": [{"name": "Demo User", "age": 26}],
    }
    quote = client.post("/api/bookings/quote", json=payload)
    assert quote.status_code == 200
    assert quote.json()["total"] > 0
    response = client.post("/api/bookings", json={**payload, "strategy": "family-aware"})
    assert response.status_code == 201
    booking = response.json()
    assert len(booking["pnr"]) == 10
    assert client.get(f"/api/bookings/{booking['pnr']}").status_code == 200
    cancelled = client.post(f"/api/bookings/{booking['pnr']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    audit = client.get("/api/admin/audit?limit=10")
    assert [row["action"] for row in audit.json()[:2]] == ["CANCEL", "BOOK"]
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["database"] == "sqlite"
    assert client.get("/healthz").json() == {"status": "ok"}
    assert "AeroReserve" in client.get("/").text


def test_invalid_passenger_count_is_rejected(
    service: FlightBookingService, travel_date: date
) -> None:
    client = TestClient(create_app(service))
    response = client.post(
        "/api/bookings",
        json={
            "flight_ids": [service.flights(travel_date)[0].flight_id],
            "travel_date": travel_date.isoformat(),
            "cabin": "Economy",
            "passengers": [],
        },
    )
    assert response.status_code == 422


def test_unknown_flight_returns_domain_error(
    service: FlightBookingService, travel_date: date
) -> None:
    client = TestClient(create_app(service))
    response = client.get(
        "/api/flights/UNKNOWN-2026-01-01/seats",
        params={"travel_date": travel_date.isoformat(), "cabin": "Economy"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_search"
