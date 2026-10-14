"""Cabin-specific aircraft seat maps and interchangeable seat selectors."""

from __future__ import annotations

from collections.abc import Iterable

from aerobooking.models import CabinClass, Seat

# rows, letters across a row, aisle after these column letters
_LAYOUTS: dict[CabinClass, tuple[int, str, frozenset[str]]] = {
    CabinClass.ECONOMY: (6, "ABCDEF", frozenset({"C"})),
    CabinClass.PREMIUM_ECONOMY: (3, "ABCD", frozenset({"B"})),
    CabinClass.BUSINESS: (2, "ABCD", frozenset({"B"})),
    CabinClass.FIRST: (1, "ABCD", frozenset({"B"})),
}

STRATEGIES = ("first-fit", "window-first", "family-aware")


def cabin_seats(cabin: CabinClass) -> tuple[Seat, ...]:
    rows, columns, aisle_after = _LAYOUTS[cabin]
    result: list[Seat] = []
    for row in range(1, rows + 1):
        for col in columns:
            result.append(
                Seat(
                    label=f"{cabin.code}{row:02d}{col}",
                    cabin=cabin,
                    row=row,
                    column=col,
                    window=col in {columns[0], columns[-1]},
                    aisle_after=col in aisle_after,
                )
            )
    return tuple(result)


def cabin_capacity(cabin: CabinClass) -> int:
    return len(cabin_seats(cabin))


def _family_block(free: list[Seat], passenger_count: int) -> tuple[Seat, ...] | None:
    """Choose an adjacent same-side seat run, avoiding the aisle gap."""
    by_row: dict[int, list[Seat]] = {}
    for seat in free:
        by_row.setdefault(seat.row, []).append(seat)
    for row in sorted(by_row):
        row_seats = sorted(by_row[row], key=lambda seat: seat.column)
        run: list[Seat] = []
        previous_index: int | None = None
        previous_seat: Seat | None = None
        for seat in row_seats:
            index = ord(seat.column) - ord("A")
            # Never call seats contiguous across the cabin aisle.
            if previous_index is not None and (
                index != previous_index + 1
                or (previous_seat is not None and previous_seat.aisle_after)
            ):
                run = []
            run.append(seat)
            previous_index = index
            previous_seat = seat
            if len(run) >= passenger_count:
                return tuple(run[:passenger_count])
    return None


def allocate_seats(
    cabin: CabinClass,
    passenger_count: int,
    occupied: Iterable[str],
    strategy: str = "family-aware",
) -> tuple[str, ...]:
    """Select seats for one flight leg; the caller handles locking and re-checks."""
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of: {', '.join(STRATEGIES)}")
    if passenger_count <= 0:
        raise ValueError("passenger_count must be positive")
    occupied_set = set(occupied)
    free = [seat for seat in cabin_seats(cabin) if seat.label not in occupied_set]
    if len(free) < passenger_count:
        raise ValueError(
            f"not enough {cabin.value} seats: {len(free)} free, {passenger_count} requested"
        )

    if strategy == "family-aware":
        block = _family_block(free, passenger_count)
        if block:
            return tuple(seat.label for seat in block)
    if strategy == "window-first":
        free.sort(key=lambda seat: (not seat.window, seat.row, seat.column))
    else:
        free.sort(key=lambda seat: (seat.row, seat.column))
    return tuple(seat.label for seat in free[:passenger_count])


def seat_map(cabin: CabinClass, occupied: Iterable[str]) -> list[dict[str, object]]:
    occupied_set = set(occupied)
    return [
        {
            "label": seat.label,
            "cabin": seat.cabin.value,
            "row": seat.row,
            "column": seat.column,
            "window": seat.window,
            "aisle_after": seat.aisle_after,
            "available": seat.label not in occupied_set,
        }
        for seat in cabin_seats(cabin)
    ]
