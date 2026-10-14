from __future__ import annotations

import pytest

from aerobooking.availability import (
    STRATEGIES,
    allocate_seats,
    cabin_capacity,
    cabin_seats,
    seat_map,
)
from aerobooking.models import CabinClass


def test_cabin_seat_counts_and_labels_are_unique() -> None:
    expected = {
        CabinClass.ECONOMY: 36,
        CabinClass.PREMIUM_ECONOMY: 12,
        CabinClass.BUSINESS: 8,
        CabinClass.FIRST: 4,
    }
    for cabin, capacity in expected.items():
        seats = cabin_seats(cabin)
        assert cabin_capacity(cabin) == capacity
        assert len({seat.label for seat in seats}) == capacity


def test_family_aware_keeps_party_in_one_row_when_possible() -> None:
    labels = allocate_seats(CabinClass.ECONOMY, 3, (), "family-aware")
    seats = {seat.label: seat for seat in cabin_seats(CabinClass.ECONOMY)}
    picked = [seats[label] for label in labels]
    assert len({seat.row for seat in picked}) == 1
    assert [seat.column for seat in picked] == ["A", "B", "C"]


def test_family_allocator_does_not_call_the_aisle_a_contiguous_gap() -> None:
    labels = allocate_seats(CabinClass.PREMIUM_ECONOMY, 3, (), "family-aware")
    # No three seats can fit on one side of a 2-2 premium row, so it falls back.
    assert labels == ("P01A", "P01B", "P01C")


def test_window_first_prefers_window_seats() -> None:
    labels = allocate_seats(CabinClass.ECONOMY, 2, (), "window-first")
    assert labels == ("E01A", "E01F")


def test_first_fit_returns_ordered_seats() -> None:
    assert allocate_seats(CabinClass.ECONOMY, 3, (), "first-fit") == (
        "E01A",
        "E01B",
        "E01C",
    )


def test_occupied_seats_are_skipped() -> None:
    labels = allocate_seats(CabinClass.ECONOMY, 2, {"E01A", "E01B"}, "first-fit")
    assert labels == ("E01C", "E01D")


def test_capacity_exhaustion_is_clear() -> None:
    occupied = {seat.label for seat in cabin_seats(CabinClass.FIRST)}
    with pytest.raises(ValueError, match="not enough First seats"):
        allocate_seats(CabinClass.FIRST, 1, occupied)


def test_unknown_strategy_is_rejected() -> None:
    with pytest.raises(ValueError, match="strategy must be one of"):
        allocate_seats(CabinClass.ECONOMY, 1, (), "random")


def test_seat_map_marks_occupied_and_window() -> None:
    rows = seat_map(CabinClass.ECONOMY, {"E01A"})
    first = rows[0]
    assert first["label"] == "E01A"
    assert first["available"] is False
    assert first["window"] is True
    assert set(STRATEGIES) == {"first-fit", "window-first", "family-aware"}
