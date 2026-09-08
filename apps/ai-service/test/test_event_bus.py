import asyncio

import pytest

from core.events import EventBus


@pytest.mark.asyncio
async def test_subscriber_replays_history_without_a_publish_gap():
    bus = EventBus()
    await bus.publish("run-1", "run.started", {"status": "RUNNING"})

    stream = bus.subscribe("run-1", after_id=0)
    first = await asyncio.wait_for(anext(stream), timeout=1)
    assert first.event_type == "run.started"

    await bus.publish("run-1", "run.completed", {"status": "COMPLETED"})
    second = await asyncio.wait_for(anext(stream), timeout=1)
    assert second.event_type == "run.completed"

    await stream.aclose()
