from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator
from datetime import date

import httpx
import uvicorn

from aerobooking.api import create_app
from aerobooking.service import FlightBookingService


def _frames(lines: Iterator[str]):
    event_name: str | None = None
    data_line: str | None = None
    for line in lines:
        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_line = line.removeprefix("data:").strip()
        elif line == "" and event_name is not None and data_line is not None:
            yield event_name, json.loads(data_line)
            event_name = None
            data_line = None


def test_live_sse_snapshot_then_booking_delta(
    service: FlightBookingService, travel_date: date
) -> None:
    flight = next(f for f in service.flights(travel_date) if f.flight_number == "AS110")
    app = create_app(service)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", lifespan="on"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.started
        with httpx.Client(timeout=8) as client:
            url = (
                f"http://127.0.0.1:{port}/api/flights/{flight.flight_id}/events"
                f"?travel_date={travel_date.isoformat()}&cabin=Economy"
            )
            with client.stream("GET", url) as response:
                assert response.status_code == 200
                frames = _frames(response.iter_lines())
                event, snapshot = next(frames)
                assert event == "snapshot"
                assert snapshot["available"] == 36
                booking_response = client.post(
                    f"http://127.0.0.1:{port}/api/bookings",
                    json={
                        "flight_ids": [flight.flight_id],
                        "travel_date": travel_date.isoformat(),
                        "cabin": "Economy",
                        "passengers": [{"name": "SSE Demo", "age": 29}],
                    },
                )
                assert booking_response.status_code == 201
                event, update = next(frames)
                assert event == "booking"
                assert update["pnr"] == booking_response.json()["pnr"]
                assert update["seat_map"]["available"] == 35
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
