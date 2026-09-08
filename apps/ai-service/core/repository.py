from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from core.events import EventBus, RunEvent, utc_now
from models.schemas import Evidence


@dataclass
class RunRecord:
    run_id: str
    workspace_id: int
    project_id: int
    user_id: int
    goal: str
    config: dict[str, Any]
    status: str = "PENDING"
    current_node: str | None = None
    progress: int = 0
    current_step: str = "等待执行"
    error_message: str | None = None
    report: dict[str, Any] | None = None
    evidence: list[Evidence] = field(default_factory=list)
    token_count: int = 0
    prompt_snapshot: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


class InMemoryRunRepository:
    """Local adapter used by the service and tests.

    The protocol is intentionally small so the Java/Postgres repository can be
    added without changing any workflow node.
    """

    def __init__(self, events: EventBus) -> None:
        self.events = events
        self._runs: dict[str, RunRecord] = {}
        self._cancelled: set[str] = set()
        self._lock = asyncio.Lock()

    async def create(self, run: RunRecord) -> RunRecord:
        async with self._lock:
            existing = self._runs.get(run.run_id)
            if existing:
                return existing
            self._runs[run.run_id] = run
            return run

    def get(self, run_id: str | int) -> RunRecord | None:
        return self._runs.get(str(run_id))

    async def update(self, run_id: str | int, **changes: Any) -> RunRecord:
        async with self._lock:
            run = self._runs[str(run_id)]
            for key, value in changes.items():
                setattr(run, key, value)
            run.updated_at = utc_now()
            return run

    async def cancel(self, run_id: str | int) -> bool:
        async with self._lock:
            key = str(run_id)
            if key not in self._runs:
                return False
            self._cancelled.add(key)
            self._runs[key].status = "CANCELLING"
            self._runs[key].updated_at = utc_now()
            return True

    def is_cancelled(self, run_id: str | int) -> bool:
        return str(run_id) in self._cancelled

    async def add_evidence(self, run_id: str | int, evidence: list[Evidence]) -> None:
        async with self._lock:
            run = self._runs[str(run_id)]
            known = {item.id for item in run.evidence}
            run.evidence.extend(item for item in evidence if item.id not in known)
            run.updated_at = utc_now()

    def list_evidence(self, run_id: str | int) -> list[Evidence]:
        run = self._runs.get(str(run_id))
        return list(run.evidence) if run else []

    def list_events(self, run_id: str | int, after_id: int = 0) -> list[RunEvent]:
        return self.events.history(run_id, after_id)
