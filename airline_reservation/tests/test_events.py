from __future__ import annotations

import asyncio

import pytest

from aerobooking.service import EventBus


@pytest.mark.asyncio
async def test_event_bus_delivers_only_to_matching_flight() -> None:
    bus = EventBus(queue_size=2)
    sub = bus.subscribe("AS101-2026-10-20")
    stream = bus.stream(sub)
    pending = asyncio.create_task(stream.__anext__())
    await asyncio.sleep(0)
    bus.publish("AS205-2026-10-20", {"kind": "booking"})
    bus.publish("AS101-2026-10-20", {"kind": "booking", "pnr": "ABC"})
    event = await asyncio.wait_for(pending, timeout=2)
    assert event["pnr"] == "ABC"
    await stream.aclose()
    assert bus.subscriber_count == 0


def test_bounded_event_queue_drops_oldest_item() -> None:
    bus = EventBus(queue_size=1)
    sub = bus.subscribe("F-1")
    bus.publish("F-1", {"kind": "booking", "number": 1})
    bus.publish("F-1", {"kind": "cancellation", "number": 2})
    assert sub.queue.get_nowait()["number"] == 2
    assert bus.subscriber_count == 1
    bus.unsubscribe(sub.id)
    assert bus.subscriber_count == 0
