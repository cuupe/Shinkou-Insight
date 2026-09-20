from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class RunEvent:
    event_id: int
    run_id: str
    event_type: str
    payload: dict[str, Any]
    timestamp: str = field(default_factory=utc_now)

    def as_sse(self) -> str:
        body = {
            "eventId": str(self.event_id),
            "runId": self.run_id,
            "timestamp": self.timestamp,
            **self.payload,
        }
        return f"id: {self.event_id}\nevent: {self.event_type}\ndata: {json.dumps(body, ensure_ascii=False)}\n\n"


class EventBus:
    """Replayable in-process bus; replaceable by Redis Streams in production."""

    def __init__(self) -> None:
        self._history: dict[str, list[RunEvent]] = {}
        self._subscribers: dict[str, set[asyncio.Queue[RunEvent | None]]] = {}
        self._next_id = 0
        self._lock = asyncio.Lock()

    async def publish(
        self, run_id: str | int, event_type: str, payload: dict[str, Any]
    ) -> RunEvent:
        async with self._lock:
            self._next_id += 1
            event = RunEvent(self._next_id, str(run_id), event_type, payload)
            self._history.setdefault(str(run_id), []).append(event)
            queues = tuple(self._subscribers.get(str(run_id), set()))
        for queue in queues:
            queue.put_nowait(event)
        return event

    def history(self, run_id: str | int, after_id: int = 0) -> list[RunEvent]:
        return [
            event
            for event in self._history.get(str(run_id), [])
            if event.event_id > after_id
        ]

    async def subscribe(
        self, run_id: str | int, after_id: int = 0
    ) -> AsyncIterator[RunEvent]:
        queue: asyncio.Queue[RunEvent | None] = asyncio.Queue()
        run_key = str(run_id)
        async with self._lock:
            self._subscribers.setdefault(run_key, set()).add(queue)
            initial_events = [
                event
                for event in self._history.get(run_key, [])
                if event.event_id > after_id
            ]
        try:
            for event in initial_events:
                yield event
            while True:
                event = await queue.get()
                if event is None:
                    return
                yield event
        finally:
            self._subscribers.get(run_key, set()).discard(queue)

    async def close(self, run_id: str | int) -> None:
        for queue in tuple(self._subscribers.get(str(run_id), set())):
            queue.put_nowait(None)
