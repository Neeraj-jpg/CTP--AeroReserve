from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest

from aerobooking.repository import BookingRepository
from aerobooking.schedule import india_today
from aerobooking.service import FlightBookingService


@pytest.fixture
def travel_date() -> date:
    return india_today() + timedelta(days=2)


@pytest.fixture
def service(tmp_path: Path) -> Iterator[FlightBookingService]:
    url = f"sqlite+pysqlite:///{tmp_path / 'aero-test.db'}"
    instance = FlightBookingService(BookingRepository(url))
    yield instance
    instance.repository.close()
